import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import './Lobby.css';

function Lobby() {
  const [codeBlocks, setCodeBlocks] = useState([]);
  
  useEffect(() => {
    const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';
    const fetchCodeBlocks = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/codeblocks`);
        setCodeBlocks(response.data);
      } catch (error) {
        console.error('Error fetching code blocks:', error);
      }
    };
    
    fetchCodeBlocks();
  }, []);
  
  return (
    <div className="lobby">
      <header className="lobby-header">
        <h1 className="main-title">JavaScript with Tom</h1>
        <p className="subtitle">Learn with the master while he's in Thailand</p>
      </header>
      
      <h2 className="section-title">Choose code block</h2>
      <div className="code-blocks-list">
        {codeBlocks.map((block) => (
          <Link 
            key={block._id} 
            to={`/codeblock/${block._id}`} 
            className="code-block-item"
          >
            {block.title}
          </Link>
        ))}
      </div>
    </div>
  );
}

export default Lobby;