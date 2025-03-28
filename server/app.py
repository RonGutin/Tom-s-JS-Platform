from flask import Flask, request, jsonify, abort
from flask_socketio import SocketIO, join_room, emit
from flask_cors import CORS
import pymongo
from bson.objectid import ObjectId
from bson.errors import InvalidId
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# MongoDB connection
try:
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client["code_blocks_db"]
    code_blocks = db["code_blocks"]
except pymongo.errors.ConnectionFailure as e:
    logger.error(f"Could not connect to MongoDB: {e}")
    raise SystemExit(1)    

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

# API endpoints
@app.route("/api/codeblocks", methods=["GET"])
def get_all_blocks():
    # Fetch all code blocks for the lobby page
    try:
        blocks = list(code_blocks.find({}, {"_id": {"$toString": "$_id"}, "title": 1, "code": 1}))
        return jsonify(blocks)
    except Exception as e:
        logger.error(f"Error fetching code blocks: {e}")
        abort(500)

@app.route("/api/codeblocks/<id>", methods=["GET"])
def get_block(id):
    # Fetch specific code block by ID
    try:
        block = code_blocks.find_one({"_id": ObjectId(id)})
        if block:
            block["_id"] = str(block["_id"])
            return jsonify(block)
        abort(404)
    except InvalidId:
        abort(400)
    except Exception as e:
        logger.error(f"Unexpected error retrieving block: {e}")
        abort(500)

# Socket events
@socketio.on("join_room")
def handle_join(data):
    room = data["room"]
    join_room(room)
    
    print(f"ROOM JOIN: User {request.sid} joining room {room}")
    try:
        # Find room in database
        block = code_blocks.find_one({"_id": ObjectId(room)})
        
        if block is None:
            # Handle case where room ID doesn't exist
            emit("room_not_found", {"message": "The requested code block doesn't exist"})
            # back to lobby
            emit("redirect_to_lobby")
            return
        
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

    except Exception as e:
        print(f"Error in join_room: {str(e)}")
        emit("error", {"message": "Server error"})

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
    code_blocks.delete_many({})
    print("Database cleared. Inserting fresh code blocks...")
    
    initial_blocks = initial_blocks = [
    {
        "title": "Declaring Variables",
        "code": "// Replace the comments below with your code\n// Declare three variables:\n// 1. A string named 'greeting' with value 'Hello world!'\n// 2. A number named 'score' with value 100\n// 3. A boolean named 'isActive' with value true",
        "originalCode": "// Replace the comments below with your code\n// Declare three variables:\n// 1. A string named 'greeting' with value 'Hello world!'\n// 2. A number named 'score' with value 100\n// 3. A boolean named 'isActive' with value true",
        "solution": "const greeting = 'Hello world!';\nconst score = 100;\nconst isActive = true;",
        "explanation": "In JavaScript, use const for values that won't change and let for variables that will change. Remember that strings need quotes, numbers don't, and booleans are either true or false.",
        "mentorId": None,
        "studentCount": 0
    },
    {
        "title": "Array Methods",
        "code": "const numbers = [1, 2, 3, 4, 5];\n// Replace this comment with code to filter even numbers",
        "originalCode": "const numbers = [1, 2, 3, 4, 5];\n// Replace this comment with code to filter even numbers",
        "solution": "const numbers = [1, 2, 3, 4, 5];\nconst evenNumbers = numbers.filter(num => num % 2 === 0);",
        "explanation": "The filter() method creates a new array with elements that pass a test. Recall the modulo operator (%) that can help identify even numbers.",
        "studentCount": 0,
        "mentorId": None
    },
    {
        "title": "String Reversal",
        "code": "function reverseString(text) {\n  // Replace this comment with code to reverse the string\n  // Return the string reversed\n}",
        "originalCode": "function reverseString(text) {\n  // Replace this comment with code to reverse the string\n  // Return the string reversed\n}",
        "solution": "function reverseString(text) {\n  return text.split('').reverse().join('');\n}",
        "explanation": "String reversal is a common coding challenge.\n Try using string methods in sequence: first split() the string into an array of characters, then reverse() the array, and finally join() it back into a string",
        "mentorId": None,
        "studentCount": 0
    },
    {
        "title": "Counter Function",
        "code": "function createCounter() {\n  // Replace this comment with code that:\n  // 1. Creates a variable to track count\n  // 2. Returns an object with three methods\n  //    - increment: increases count by 1\n  //    - decrement: decreases count by 1\n  //    - getValue: returns current count\n}",
        "originalCode": "function createCounter() {\n  // Replace this comment with code that:\n  // 1. Creates a variable to track count\n  // 2. Returns an object with three methods\n  //    - increment: increases count by 1\n  //    - decrement: decreases count by 1\n  //    - getValue: returns current count\n}",
        "solution": "function createCounter() {\n  let count = 0;\n  return {\n    increment: function() { count++; },\n    decrement: function() { count--; },\n    getValue: function() { return count; }\n  };\n}",
        "explanation": "Use a closure to preserve the counter variable. Define a local variable inside the outer function, then return an object with methods that can access that variable even after the outer function completes.",
        "mentorId": None,
        "studentCount": 0
    },
    {
        "title": "Async Function",
        "code": "async function fetchData() {\n  // Replace this comment with code that:\n  // 1. Fetches data from 'https://api.example.com/data'\n  // 2. Parses the JSON response\n  // 3. Returns the parsed data\n}",
        "originalCode": "async function fetchData() {\n  // Replace this comment with code that:\n  // 1. Fetches data from 'https://api.example.com/data'\n  // 2. Parses the JSON response\n  // 3. Returns the parsed data\n}",
        "solution": "async function fetchData() {\n  const response = await fetch('https://api.example.com/data');\n  const data = await response.json();\n  return data;\n}",
        "explanation": "The async keyword lets you use await to pause execution until a Promise resolves. This makes asynchronous code much easier to read and write compared to Promise chains.",
        "studentCount": 0,
        "mentorId": None
    },
    {
        "title": "DOM Manipulation",
        "code": "// Replace this comment with a function called addElement that:\n// 1. Takes a text parameter\n// 2. Creates a new div element\n// 3. Sets the div's text content to the parameter\n// 4. Adds the div to the document body\n// 5. Returns the created element",
        "originalCode": "// Replace this comment with a function called addElement that:\n// 1. Takes a text parameter\n// 2. Creates a new div element\n// 3. Sets the div's text content to the parameter\n// 4. Adds the div to the document body\n// 5. Returns the created element",
        "solution": "function addElement(text) {\n  const newDiv = document.createElement('div');\n  newDiv.textContent = text;\n  document.body.appendChild(newDiv);\n  return newDiv;\n}",
        "explanation": "Remember the three steps: create an element with document.createElement(), modify its properties, and append it to the document with appendChild(). Don't forget to return the created element.",
        "studentCount": 0,
        "mentorId": None
    }
]
    
    code_blocks.insert_many(initial_blocks)

    socketio.run(app, debug=True, port=5000)