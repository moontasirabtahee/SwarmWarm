import os
import secrets
import base64

def init_project():
    print("================================================================================")
    # 1. Directory scaffolding mapping
    directories = [
        "app",
        "app/core",
        "app/api",
        "app/api/v1",
        "app/workers",
        "app/models",
        "scripts"
    ]
    
    print("Creating core repository directories...")
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f" [+] Created directory: {directory}")
        else:
            print(f" [.] Directory already exists: {directory}")
            
    # Create empty __init__.py files for package structure
    package_roots = ["app", "app/core", "app/api", "app/api/v1", "app/workers", "app/models"]
    for pr in package_roots:
        init_file = os.path.join(pr, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write(f"# Package initialization for {pr}\n")
            print(f" [+] Created: {init_file}")

    # 2. Automatically generate the standard .gitignore
    print("\nGenerating standard .gitignore file...")
    gitignore_content = """# Virtual Environment
.venv/
venv/
ENV/

# Local configuration
.env

# Python compilation files
__pycache__/
*.pyc
*.pyo
*.pyd

# Distribution / packaging
build/
dist/
*.egg-info/

# Logs
logs/
*.log
"""
    with open(".gitignore", "w") as f:
        f.write(gitignore_content.strip() + "\n")
    print(" [+] Created: .gitignore")

    # 3. Generate dummy .env filled with correctly formatted placeholder structures
    print("\nGenerating local .env file...")
    
    # Generate cryptographic keys
    jwt_secret = secrets.token_urlsafe(32)
    decryption_key = secrets.token_bytes(32).hex()
    
    env_content = f"""# ==============================================================================
# SWARMWARM LOCAL DEVELOPMENT CONFIGURATION (AUTO-GENERATED)
# ==============================================================================

# Web Server Parameters
PORT=8000
ENV=development

# Cryptographic Keys
# Auto-generated 32-byte secure JWT secret token
SWARMWARM_SECRET_KEY={jwt_secret}
# Auto-generated 32-byte secure hex decryption key (64 hex characters) for AES-GCM
SWARMWARM_DECRYPTION_KEY={decryption_key}

# Supabase Database Configuration
SUPABASE_URL=https://your-supabase-project-id.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_jwt_token

# Redis Broker Configuration
REDIS_BROKER_URL=redis://localhost:6379/0

# Local AI microservice routes
LOCAL_AI_TUNNEL_URL=https://your-cloudflare-tunnel.trycloudflare.com
LOCAL_AI_API_KEY=your_local_ai_authentication_bearer_token
"""
    with open(".env", "w") as f:
        f.write(env_content.strip() + "\n")
    print(" [+] Created: .env")
    
    print("\n================================================================================")
    print("                 SWARMWARM INITIALIZATION PROCESS COMPLETE")
    print("================================================================================")

if __name__ == "__main__":
    init_project()
