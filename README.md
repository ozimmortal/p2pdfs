# P2P Distributed File Sharing System

A peer-to-peer distributed file sharing system implemented in Python, featuring a central tracker server for peer coordination and a peer implementation that can both share and download files.

## Features

- Central tracker server for peer coordination
- File chunking for efficient transfer
- SQLite database for both tracker and peers
- Multiple peer support
- Concurrent file sharing and downloading

## Setup

1. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Tracker Server

Start the central tracker server first:

```bash
python tracker.py
```

The tracker will run on `http://localhost:5000`.

### Running Peers

You can run multiple peers on different ports. Each peer can share and download files.

To share a file:
```bash
python peer.py <port> share <filepath>
```
Example:
```bash
python peer.py 5001 share myfile.txt
```

To download a file:
```bash
python peer.py <port> download <file_id> <output_path>
```
Example:
```bash
python peer.py 5002 download 1 downloaded_file.txt
```
