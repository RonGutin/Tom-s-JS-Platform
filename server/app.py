from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_cors import CORS
import pymongo
from bson.objectid import ObjectId

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

room_mentors = {}

# MongoDB connection
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["code_blocks_db"]
code_blocks = db["code_blocks"]

# API endpoints
@app.route("/api/codeblocks", methods=["GET"])
def get_all_blocks():
    # Fetch all code blocks for the lobby page
    blocks = list(code_blocks.find({}, {"_id": {"$toString": "$_id"}, "title": 1, "code": 1}))
    return jsonify(blocks)

@app.route("/api/codeblocks/<id>", methods=["GET"])
def get_block(id):
    # Fetch specific code block by ID
    block = code_blocks.find_one({"_id": ObjectId(id)})
    if block:
        block["_id"] = str(block["_id"])
        print(f"block id mongo -> {str(block["_id"])}")
        return jsonify(block)
    return jsonify({"error": "Block not found"}), 404

# Socket events

@socketio.on("join_room")
def handle_join(data):
    room = data["room"]
    join_room(room)
    
    print(f"JOIN: User {request.sid} joining room {room}")
    
    # Find room in database
    block = code_blocks.find_one({"_id": ObjectId(room)})
    
    # First visitor to this specific room is the mentor
    is_mentor = block.get("mentorId") is None
    
    if is_mentor:
        # Set this user as mentor for this room
        code_blocks.update_one(
            {"_id": ObjectId(room)},
            {"$set": {"mentorId": request.sid}}
        )
        print(f"User {request.sid} set as mentor for room {room}")
    else:
        # Increment student count
        code_blocks.update_one(
            {"_id": ObjectId(room)},
            {"$inc": {"studentCount": 1}}
        )
        print(f"Student joined room {room}, incrementing count")
    
    # Send role to client
    emit("role_assigned", {"isMentor": is_mentor})
    
    # Update everyone with current count
    updated_block = code_blocks.find_one({"_id": ObjectId(room)})
    emit("room_update", {"studentCount": updated_block["studentCount"]}, to=room)

@socketio.on("disconnect")
def handle_disconnect():
    # Find rooms this user was in
    for room in socketio.server.rooms(request.sid):
        if room != request.sid:  # Skip socket's own room
            # Check if this user was the mentor of this room
            block = code_blocks.find_one({"_id": ObjectId(room)})
            
            if block and block.get("mentorId") == request.sid:
                print(f"Mentor leaving room {room}")
                # Reset room when mentor leaves
                code_blocks.update_one(
                    {"_id": ObjectId(room)},
                    {"$set": {
                        "code": block["originalCode"], 
                        "studentCount": 0,
                        "mentorId": None
                    }}
                )
                # Tell students to go back to lobby
                emit("mentor_left", to=room)
            else:
                print(f"Student leaving room {room}")
                # Update student count only if it's positive
                current_count = block.get("studentCount", 0)
                if current_count > 0:
                    code_blocks.update_one(
                        {"_id": ObjectId(room)},
                        {"$inc": {"studentCount": -1}}
                    )
                    # Update everyone
                    updated_block = code_blocks.find_one({"_id": ObjectId(room)})
                    emit("room_update", {"studentCount": updated_block["studentCount"]}, to=room)

@socketio.on("code_change")
def handle_code_change(data):
    room = data["room"]
    code = data["code"]
    # Save the updated code in the database
    code_blocks.update_one(
        {"_id": ObjectId(room)},
        {"$set": {"code": code}}
    )
    
    # Check if code matches the solution
    block = code_blocks.find_one({"_id": ObjectId(room)})
    is_solved = code.strip() == block["solution"].strip()
    
    # Send update to all users in the room
    emit("code_update", {"code": code, "isSolved": is_solved}, to=room)

if __name__ == "__main__":
    # Reset all code blocks to original state on server restart
    for block in code_blocks.find():
        code_blocks.update_one(
            {"_id": block["_id"]},
            {"$set": {"code": block["originalCode"], "studentCount": 0, "mentorId": None}}
        )
    # Clear room mentors on restart
    room_mentors.clear()

    # Create initial data if none exists
    if code_blocks.count_documents({}) == 0:
        initial_blocks = [
            {
                "title": "Async Function",
                "code": "async function fetchData() {\n  // Complete code here\n}",
                "originalCode": "async function fetchData() {\n  // Complete code here\n}",
                "solution": "async function fetchData() {\n  const response = await fetch('https://api.example.com/data');\n  const data = await response.json();\n  return data;\n}",
                "studentCount": 0,
                "mentorId": None
            },
            {
                "title": "Array Methods",
                "code": "const numbers = [1, 2, 3, 4, 5];\n// Filter even numbers",
                "originalCode": "const numbers = [1, 2, 3, 4, 5];\n// Filter even numbers",
                "solution": "const numbers = [1, 2, 3, 4, 5];\nconst evenNumbers = numbers.filter(num => num % 2 === 0);",
                "studentCount": 0,
                "mentorId": None
            },
            {
                "title": "Promise Chain",
                "code": "function processData() {\n  // Create a promise chain\n}",
                "originalCode": "function processData() {\n  // Create a promise chain\n}",
                "solution": "function processData() {\n  return fetch('https://api.example.com/data')\n    .then(response => response.json())\n    .then(data => data.filter(item => item.active))\n    .catch(error => console.error(error));\n}",
                "studentCount": 0,
                "mentorId": None
            },
            {
                "title": "DOM Manipulation",
                "code": "// Create a function to add a new element to the page",
                "originalCode": "// Create a function to add a new element to the page",
                "solution": "function addElement(text) {\n  const newDiv = document.createElement('div');\n  newDiv.textContent = text;\n  document.body.appendChild(newDiv);\n  return newDiv;\n}",
                "studentCount": 0,
                "mentorId": None
            }
        ]
        code_blocks.insert_many(initial_blocks)
    
    socketio.run(app, debug=True, port=5000)