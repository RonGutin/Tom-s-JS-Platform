import logging
import pymongo
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, abort
from flask_socketio import SocketIO, join_room, emit
from flask_cors import CORS
from bson.objectid import ObjectId
from bson.errors import InvalidId

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=[
    "http://localhost:3000",  
    os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    ])
socketio = SocketIO(app, cors_allowed_origins="*")

# MongoDB connection
try:
    mongodb_uri = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
    client = pymongo.MongoClient(mongodb_uri)
    db = client["code_blocks_db"]
    code_blocks = db["code_blocks"]
except pymongo.errors.ConnectionFailure as e:
    logger.error(f"Could not connect to MongoDB: {e}")
    raise SystemExit(1)    

def initialize_database():
    if code_blocks.count_documents({}) == 0:
        print("Database empty. Inserting initial code blocks...")
        
        initial_blocks = [
            # Your blocks here...
        ]
        
        code_blocks.insert_many(initial_blocks)
    else:
        print(f"Database already contains {code_blocks.count_documents({})} code blocks")

    # Reset student counts and mentor assignments
    code_blocks.update_many({}, {"$set": {"studentCount": 0, "mentorId": None}})

initialize_database()

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
    sender = data["sender"]
    # Save the updated code in the database
    code_blocks.update_one(
        {"_id": ObjectId(room)},
        {"$set": {"code": code}}
    )
    
    # Check if code matches the solution
    block = code_blocks.find_one({"_id": ObjectId(room)})
    is_solved = code.strip() == block["solution"].strip()
    
    # Send update to all users in the room
    emit("code_update", {"code": code, "isSolved": is_solved, "sender":sender}, to=room)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))

    if os.environ.get('ENVIRONMENT') == 'production':
        socketio.run(app, host='0.0.0.0', port=port, cors_allowed_origins="*")
    else:
        # For development (Local)
        socketio.run(app, debug=True, port=port)