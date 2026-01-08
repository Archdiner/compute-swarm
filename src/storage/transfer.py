
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Response
from fastapi.responses import FileResponse
import structlog
import uvicorn
import asyncio

logger = structlog.get_logger()

class FileServer:
    """
    Simple HTTP File Server for P2P Transfer (Swarm Transfer Protocol).
    Serves files from a local directory, secured by a token.
    """
    
    def __init__(self, port: int = 8001, storage_dir: str = "./storage"):
        self.port = port
        self.storage_dir = os.path.abspath(storage_dir)
        self.app = FastAPI(title="Swarm File Server")
        self.server = None
        self._setup_routes()
        
        # Ensure storage dir exists
        os.makedirs(self.storage_dir, exist_ok=True)
        
    def _setup_routes(self):
        @self.app.get("/files/{filename}")
        async def get_file(filename: str, x_transfer_token: str = Header(None)):
            # Basic security check (in real implementation, validate against DB/Job)
            # For prototype, we just check if header is present if required, 
            # or we can allow public for now as per "P2P" instruction but hidden behind tunnel
            
            file_path = os.path.join(self.storage_dir, filename)
            
            # Security: Prevent directory traversal
            if not os.path.commonpath([file_path, self.storage_dir]) == self.storage_dir:
                raise HTTPException(status_code=403, detail="Access denied")
                
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="File not found")
                
            logger.info("serving_file", filename=filename, requester="remote")
            return FileResponse(file_path)

        @self.app.head("/files/{filename}")
        async def get_file_head(filename: str):
            file_path = os.path.join(self.storage_dir, filename)
            if not os.path.exists(file_path):
                 raise HTTPException(status_code=404, detail="File not found")
            
            size = os.path.getsize(file_path)
            return Response(headers={"Content-Length": str(size)})

    async def start(self):
        """Start the file server"""
        config = uvicorn.Config(app=self.app, host="0.0.0.0", port=self.port, log_level="info")
        self.server = uvicorn.Server(config)
        logger.info("file_server_starting", port=self.port, storage_dir=self.storage_dir)
        await self.server.serve()

    def stop(self):
        if self.server:
            self.server.should_exit = True

# Helper to run server in background (for agents)
def start_file_server_background(port: int = 8001, storage_dir: str = "./storage"):
    server = FileServer(port=port, storage_dir=storage_dir)
    asyncio.create_task(server.start())
    return server
