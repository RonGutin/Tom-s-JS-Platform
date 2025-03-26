import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { io } from 'socket.io-client';
import axios from 'axios';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';
import 'prismjs/components/prism-javascript';
import './CodeBlock.css';
import CodeMirror from '@uiw/react-codemirror';
import { javascript } from '@codemirror/lang-javascript';

function CodeBlock() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [codeBlock, setCodeBlock] = useState(null);
  const [code, setCode] = useState('');
  const [isMentor, setIsMentor] = useState(false);
  const [studentCount, setStudentCount] = useState(0);
  const [isSolved, setIsSolved] = useState(false);
  const socketRef = useRef();

  useEffect(() => {
    // Fetch code block data
    const fetchCodeBlock = async () => {
      try {
        const response = await axios.get(`http://localhost:5000/api/codeblocks/${id}`);
        setCodeBlock(response.data);
        setCode(response.data.code);
      } catch (error) {
        console.error('Error fetching code block:', error);
      }
    };

    fetchCodeBlock();

    // Setup Socket.IO connection
    socketRef.current = io('http://localhost:5000');
    
    // Join the room
    socketRef.current.emit('join_room', { room: id });
    
    // Listen for role assignment
    socketRef.current.on('role_assigned', (data) => {
      setIsMentor(data.isMentor);
    });

    // Listen for room updates
    socketRef.current.on('room_update', (data) => {
      setStudentCount(data.studentCount);
    });

    // Listen for code updates
    socketRef.current.on('code_update', (data) => {
      setCode(data.code);
      setIsSolved(data.isSolved);
    });
    
    // Listen for mentor leaving
    socketRef.current.on('mentor_left', () => {
      navigate('/');
    });

    // Cleanup on unmount
    return () => {
      socketRef.current.disconnect();
    };
  }, [id, navigate]);

  // Handle code changes
  const handleCodeChange = (value) => {
    setCode(value);
    socketRef.current.emit('code_change', { room: id, code: value });
  };

  // Handle back button click
  const handleBackClick = () => {
    navigate('/');
  };
    // Apply syntax highlighting after code updates
    useEffect(() => {
        if (codeBlock) {
            Prism.highlightAll();
        }
        }, [code, codeBlock]);

  if (!codeBlock) {
    return <div>Loading...</div>;
  }

  return (
    <div className="code-block-container">
      <div className="code-block-header">
        <h2>{codeBlock.title}</h2>
        <div className="status-container">
          <button className="back-button" onClick={handleBackClick}>Back to Lobby</button>
          <div className="role-indicator">Role: {isMentor ? 'Mentor' : 'Student'}</div>
          <div className="student-count">Students in room: {studentCount}</div>
        </div>
      </div>
      
      {isSolved && (
        <div className="solved-indicator">
          <span className="smiley">😊</span>
          <span>Great job! The solution is correct!</span>
        </div>
      )}
      
      <div className="code-editor-container">
        <CodeMirror
            value={code}
            height="400px"
            extensions={[javascript()]}
            onChange={handleCodeChange}
            readOnly={isMentor}
            theme="light"
            basicSetup={{
                autocompletion: false,
                lineNumbers: true,
                indentOnInput: true
            }}
            style={{ textAlign: 'left' }}
        />
      </div>
    </div>
  );
}

export default CodeBlock;