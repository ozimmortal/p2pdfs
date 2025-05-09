from flask import Flask, request, jsonify, send_file, render_template
import requests
import os
import hashlib
import sqlite3
from threading import Thread
import math
import json
from datetime import datetime
import io
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1MB chunks
TRACKER_URL = "http://localhost:5000"

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('peer.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            file_id INTEGER,
            chunk_number INTEGER,
            chunk_data BLOB,
            PRIMARY KEY (file_id, chunk_number)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS files (
            file_id INTEGER PRIMARY KEY,
            filename TEXT,
            total_chunks INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def split_file(filepath, file_id):
    """Split a file into chunks and return total chunks."""
    file_size = os.path.getsize(filepath)
    total_chunks = math.ceil(file_size / CHUNK_SIZE)
    logger.debug(f"Splitting file {filepath} into {total_chunks} chunks")
    
    with open(filepath, 'rb') as f:
        chunk_number = 0
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            
            logger.debug(f"Processing chunk {chunk_number}, size: {len(chunk)} bytes")
            conn = sqlite3.connect('peer.db')
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO chunks (file_id, chunk_number, chunk_data) VALUES (?, ?, ?)',
                     (file_id, chunk_number, chunk))
            conn.commit()
            conn.close()
            logger.debug(f"Stored chunk {chunk_number} in database")
            
            chunk_number += 1
    
    return total_chunks

def register_with_tracker(filename, total_chunks):
    """Register file with the tracker server."""
    logger.debug(f"Registering file {filename} with {total_chunks} chunks")
    response = requests.post(f"{TRACKER_URL}/register", json={
        "filename": filename,
        "total_chunks": total_chunks
    })
    logger.debug(f"Tracker response: {response.json()}")
    return response.json()

def update_chunk_location(file_id, chunk_number, peer_address):
    """Update tracker with chunk location."""
    logger.debug(f"Updating tracker for chunk {chunk_number} of file {file_id} at {peer_address}")
    try:
        data = {
            "file_id": int(file_id),  # Ensure file_id is an integer
            "chunk_number": int(chunk_number),  # Ensure chunk_number is an integer
            "peer_address": peer_address
        }
        logger.debug(f"Sending update data to tracker: {data}")
        response = requests.post(f"{TRACKER_URL}/update_chunk", json=data)
        response.raise_for_status()  # Raise an exception for bad status codes
        logger.debug(f"Tracker update response: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to update chunk location: {str(e)}")
        return None

@app.route('/chunk/<int:file_id>/<int:chunk_number>', methods=['GET'])
def get_chunk(file_id, chunk_number):
    """Serve a specific chunk to other peers."""
    logger.debug(f"Received request for chunk {chunk_number} of file {file_id}")
    conn = sqlite3.connect('peer.db')
    c = conn.cursor()
    c.execute('SELECT chunk_data FROM chunks WHERE file_id = ? AND chunk_number = ?',
             (file_id, chunk_number))
    result = c.fetchone()
    conn.close()
    
    if result is None:
        logger.error(f"Chunk {chunk_number} of file {file_id} not found in database")
        return jsonify({'error': 'Chunk not found'}), 404
    
    logger.debug(f"Sending chunk {chunk_number} of file {file_id}, size: {len(result[0])} bytes")
    return send_file(
        io.BytesIO(result[0]),
        mimetype='application/octet-stream',
        as_attachment=True,
        download_name=f'chunk_{file_id}_{chunk_number}'
    )

def share_file(filepath):
    """Share a file by splitting it and registering with tracker."""
    logger.debug(f"Starting to share file: {filepath}")
    filename = os.path.basename(filepath)
    
    # First register with tracker to get file_id
    file_size = os.path.getsize(filepath)
    total_chunks = math.ceil(file_size / CHUNK_SIZE)
    logger.debug(f"File size: {file_size} bytes, total chunks: {total_chunks}")
    
    response = register_with_tracker(filename, total_chunks)
    file_id = response['file_id']
    logger.debug(f"Received file_id: {file_id} from tracker")
    
    # Store file metadata locally
    conn = sqlite3.connect('peer.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO files (file_id, filename, total_chunks) VALUES (?, ?, ?)',
             (file_id, filename, total_chunks))
    conn.commit()
    conn.close()
    
    # Now split file using the correct file_id
    split_file(filepath, file_id)
    
    # Update tracker with chunk locations
    peer_address = f"http://localhost:{app.config['PORT']}"
    for chunk_number in range(total_chunks):
        update_chunk_location(file_id, chunk_number, peer_address)
    
    logger.debug(f"File sharing complete. File ID: {file_id}")
    return file_id

def download_chunk(peer_address, file_id, chunk_number):
    """Download a specific chunk from a peer."""
    logger.debug(f"Downloading chunk {chunk_number} of file {file_id} from {peer_address}")
    try:
        response = requests.get(f"{peer_address}/chunk/{file_id}/{chunk_number}", timeout=10)
        if response.status_code == 200:
            chunk_data = response.content
            logger.debug(f"Successfully downloaded chunk {chunk_number}, size: {len(chunk_data)} bytes")
            
            # Store the chunk in our local database
            conn = sqlite3.connect('peer.db')
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO chunks (file_id, chunk_number, chunk_data) VALUES (?, ?, ?)',
                     (file_id, chunk_number, chunk_data))
            conn.commit()
            conn.close()
            logger.debug(f"Stored chunk {chunk_number} in local database")
            
            return chunk_data
        else:
            logger.error(f"Failed to download chunk {chunk_number} from {peer_address}: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error downloading chunk {chunk_number}: {str(e)}")
        return None

def download_file(file_id, output_path):
    """Download a file by getting chunks from various peers."""
    logger.debug(f"Starting download of file {file_id} to {output_path}")
    
    # Get peer information from tracker
    try:
        response = requests.get(f"{TRACKER_URL}/get_peers", params={'file_id': file_id}, timeout=10)
        response.raise_for_status()
        chunk_peers = response.json()
        logger.debug(f"Received peer information: {chunk_peers}")
    except Exception as e:
        logger.error(f"Failed to get peer information: {str(e)}")
        raise Exception("Failed to get peer information from tracker")
    
    # Create the output file
    with open(output_path, 'wb') as f:
        for chunk_number in sorted(map(int, chunk_peers.keys())):
            peers = chunk_peers[str(chunk_number)]
            chunk_data = None
            logger.debug(f"Processing chunk {chunk_number}, available peers: {len(peers)}")
            
            # Try each peer until successful
            for peer in peers:
                chunk_data = download_chunk(peer['peer_address'], file_id, chunk_number)
                if chunk_data:
                    f.write(chunk_data)
                    logger.debug(f"Wrote chunk {chunk_number} to output file")
                    break
            
            if not chunk_data:
                error_msg = f"Failed to download chunk {chunk_number} from any peer"
                logger.error(error_msg)
                raise Exception(error_msg)
    
    logger.debug(f"File download complete: {output_path}")
    return True

@app.route('/')
def index():
    """Serve the main UI page."""
    return render_template('index.html')

@app.route('/api/share', methods=['POST'])
def api_share():
    """API endpoint for sharing a file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save the file temporarily
    temp_path = os.path.join('temp', file.filename)
    os.makedirs('temp', exist_ok=True)
    file.save(temp_path)
    
    try:
        file_id = share_file(temp_path)
        return jsonify({
            'success': True,
            'file_id': file_id,
            'filename': file.filename
        })
    except Exception as e:
        logger.error(f"Error sharing file: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/api/download', methods=['POST'])
def api_download():
    """API endpoint for downloading a file."""
    data = request.json
    if not data or 'file_id' not in data or 'output_path' not in data:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        file_id = int(data['file_id'])
        output_path =   data['output_path']
        
        # Start download in a separate thread
        thread = Thread(target=download_file, args=(file_id, output_path))
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Download started'
        })
    except Exception as e:
        logger.error(f"Error starting download: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python peer.py <port>")
        sys.exit(1)
    
    port = int(sys.argv[1])
    app.config['PORT'] = port
    app.run(host='0.0.0.0', port=port, debug=True)