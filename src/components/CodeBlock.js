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
import Confetti from 'react-confetti';

function CodeBlock() {
    // roomID
  const { id } = useParams();
  const navigate = useNavigate();
  const [codeBlock, setCodeBlock] = useState(null);
  const [code, setCode] = useState('');
  const [isMentor, setIsMentor] = useState(false);
  const [studentCount, setStudentCount] = useState(0);
  const [isSolved, setIsSolved] = useState(false);
  const socketRef = useRef();
  const [windowSize, setWindowSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  useEffect(() => {
    // Fetch code block data
    const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';
    const fetchCodeBlock = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/codeblocks/${id}`);
        setCodeBlock(response.data);
        setCode(response.data.code);
      } catch (error) {
        console.error('Error fetching code block:', error);
      }
    };

    fetchCodeBlock();

    // Setup Socket.IO connection
    socketRef.current = io(API_BASE_URL, {
      transports: ['websocket', 'polling'],  
      reconnection: true,
    });
    
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
      console.log('Code update received:', data);
      console.log('My socket ID:', socketRef.current.id);
      console.log('Sender socket ID:', data.sender);

      if (data.sender !== socketRef.current.id){
        setCode(data.code);
      }  
      setIsSolved(data.isSolved);
    });
    
    // Listen for mentor leaving
    socketRef.current.on('mentor_left', () => {
      navigate('/');
    });

    socketRef.current.on('room_not_found', (data) => {
      alert(data.message);
      navigate('/');
    });
    
    socketRef.current.on('redirect_to_lobby', () => {
      navigate('/');
    });
    
    socketRef.current.on('error', (data) => {
      alert(`Error: ${data.message}`);
    });

    // Cleanup on unmount
    return () => {
      socketRef.current.disconnect();
    };
  }, [id, navigate]);


  // Apply syntax highlighting after code updates
  useEffect(() => {
      if (codeBlock) {
          Prism.highlightAll();
      }
      }, [code, codeBlock]);

  useEffect(() => {
      const updateWindowDimensions = () => {
        setWindowSize({
          width: window.innerWidth,
          height: window.innerHeight
        });
      };
      // Set initial size
      updateWindowDimensions();
    
      // Update when window resizes
      window.addEventListener('resize', updateWindowDimensions);
    
    return () => window.removeEventListener('resize', updateWindowDimensions);
  }, []);
      
  // Handle code changes
  const handleCodeChange = (value) => {
    console.log('Sending code change, my ID:', socketRef.current.id);
    setCode(value);
    socketRef.current.emit('code_change', { room: id, code: value, sender: socketRef.current.id });
  };

  // Handle back button click
  const handleBackClick = () => {
    navigate('/');
  };

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
        <>
            <Confetti
            width={windowSize.width}
            height={windowSize.height}
            recycle={false}
            numberOfPieces={500}
            gravity={0.3}
            />
            <div className="solved-indicator">
            <span className="smiley">😊</span>
            <span>Great job! The solution is correct!</span>
            </div>
        </>
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

      {codeBlock.explanation && (
        <div className="explanation-box">
            <div className="explanation-title">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4682B4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="16" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
            Tom's Tips
            </div>
            <div className="explanation-content">
            {codeBlock.explanation}
            </div>
        </div>
        )}
    </div>
  );
}

export default CodeBlock;