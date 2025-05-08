import sqlite3
from flask import Flask, request, jsonify
from datetime import datetime
import os
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('tracker.db')
    c = conn.cursor()
    
    # Create files table
    c.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            total_chunks INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create chunks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            chunk_number INTEGER NOT NULL,
            peer_address TEXT NOT NULL,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

@app.route('/register', methods=['POST'])
def register_file():
    data = request.json
    filename = data.get('filename')
    total_chunks = data.get('total_chunks')
    
    if not filename or not total_chunks:
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = sqlite3.connect('tracker.db')
    c = conn.cursor()
    
    try:
        c.execute('INSERT INTO files (filename, total_chunks) VALUES (?, ?)',
                 (filename, total_chunks))
        file_id = c.lastrowid
        conn.commit()
        
        return jsonify({
            'file_id': file_id,
            'message': 'File registered successfully'
        })
    finally:
        conn.close()

@app.route('/update_chunk', methods=['POST'])
def update_chunk():
    data = request.json
    logger.debug(f"Received update_chunk request with data: {data}")
    
    try:
        file_id = int(data.get('file_id'))
        chunk_number = int(data.get('chunk_number'))
        peer_address = data.get('peer_address')
        
        if not all([file_id, chunk_number is not None, peer_address]):
            missing = []
            if not file_id:
                missing.append('file_id')
            if chunk_number is None:
                missing.append('chunk_number')
            if not peer_address:
                missing.append('peer_address')
            return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
        
        conn = sqlite3.connect('tracker.db')
        c = conn.cursor()
        
        try:
            # Verify file exists
            c.execute('SELECT id FROM files WHERE id = ?', (file_id,))
            if not c.fetchone():
                return jsonify({'error': f'File ID {file_id} not found'}), 404
            
            # Check if chunk exists
            c.execute('''
                SELECT id FROM chunks 
                WHERE file_id = ? AND chunk_number = ? AND peer_address = ?
            ''', (file_id, chunk_number, peer_address))
            
            if c.fetchone():
                # Update last_seen
                c.execute('''
                    UPDATE chunks 
                    SET last_seen = CURRENT_TIMESTAMP 
                    WHERE file_id = ? AND chunk_number = ? AND peer_address = ?
                ''', (file_id, chunk_number, peer_address))
                logger.debug(f"Updated existing chunk record")
            else:
                # Insert new chunk
                c.execute('''
                    INSERT INTO chunks (file_id, chunk_number, peer_address)
                    VALUES (?, ?, ?)
                ''', (file_id, chunk_number, peer_address))
                logger.debug(f"Inserted new chunk record")
            
            conn.commit()
            return jsonify({'message': 'Chunk updated successfully'})
        finally:
            conn.close()
            
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid data format: {str(e)}")
        return jsonify({'error': f'Invalid data format: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/get_peers', methods=['GET'])
def get_peers():
    file_id = request.args.get('file_id')
    if not file_id:
        return jsonify({'error': 'Missing file_id'}), 400
    
    try:
        file_id = int(file_id)
    except ValueError:
        return jsonify({'error': 'Invalid file_id format'}), 400
    
    conn = sqlite3.connect('tracker.db')
    c = conn.cursor()
    
    try:
        # Verify file exists
        c.execute('SELECT id FROM files WHERE id = ?', (file_id,))
        if not c.fetchone():
            return jsonify({'error': f'File ID {file_id} not found'}), 404
        
        # Get all chunks for the file
        c.execute('''
            SELECT chunk_number, peer_address, last_seen
            FROM chunks
            WHERE file_id = ?
            ORDER BY chunk_number
        ''', (file_id,))
        
        chunks = c.fetchall()
        result = {}
        
        for chunk_number, peer_address, last_seen in chunks:
            if chunk_number not in result:
                result[chunk_number] = []
            result[chunk_number].append({
                'peer_address': peer_address,
                'last_seen': last_seen
            })
        
        return jsonify(result)
    finally:
        conn.close()

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)