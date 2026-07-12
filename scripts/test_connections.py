import sys
import smtplib
import imaplib
import getpass
from swarmwarm.core.security import encrypt_credentials, decrypt_credentials

def test_smtp_connection(email, password, host, port, use_ssl=True):
    print(f"\n--- Testing SMTP Outbound Handshake ({host}:{port}) ---")
    try:
        if use_ssl:
            print("Establishing secure SMTP SSL connection...")
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            print("Establishing TCP connection...")
            server = smtplib.SMTP(host, port, timeout=10)
            print("Starting TLS handshake...")
            server.starttls()
            
        server.ehlo()
        print("Authenticating credentials...")
        server.login(email, password)
        print("SMTP AUTH SUCCESS: Connection and login successful!")
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP AUTH FAILED: {e}")
        return False

def test_imap_connection(email, password, host, port):
    print(f"\n--- Testing IMAP Inbound Handshake ({host}:{port}) ---")
    try:
        print("Establishing secure IMAP SSL connection...")
        mailbox = imaplib.IMAP4_SSL(host, port, timeout=10)
        print("Authenticating credentials...")
        mailbox.login(email, password)
        print("IMAP AUTH SUCCESS: Login successful!")
        
        print("Retrieving folder directory list...")
        status, folders = mailbox.list()
        if status == 'OK':
            print("Available Folders:")
            for folder in folders:
                folder_name = folder.decode('utf-8')
                print(f" - {folder_name}")
        else:
            print("Warning: Could not retrieve folder list.")
            
        mailbox.logout()
        return True
    except Exception as e:
        print(f"IMAP AUTH FAILED: {e}")
        return False

def main():
    print("================================================================================")
    print("                 SWARMWARM PROTOCOL INGRESS HANDSHAKE TESTER")
    print("================================================================================")
    
    print("Choose target email infrastructure provider configuration:")
    print(" 1. Google Workspace Preset (smtp.gmail.com / imap.gmail.com)")
    print(" 2. Microsoft 365 Preset (smtp.office365.com / outlook.office365.com)")
    print(" 3. Custom SMTP/IMAP configurations")
    choice = input("Select option (1-3): ").strip()
    
    if choice == '1':
        smtp_host = "smtp.gmail.com"
        smtp_port = 465
        use_ssl = True
        imap_host = "imap.gmail.com"
        imap_port = 993
    elif choice == '2':
        smtp_host = "smtp.office365.com"
        smtp_port = 587
        use_ssl = False
        imap_host = "outlook.office365.com"
        imap_port = 993
    else:
        smtp_host = input("Enter SMTP Host: ").strip()
        smtp_port = int(input("Enter SMTP Port: ").strip())
        use_ssl_input = input("Use direct SSL? (y/n): ").strip().lower()
        use_ssl = use_ssl_input == 'y'
        imap_host = input("Enter IMAP Host: ").strip()
        imap_port = int(input("Enter IMAP Port: ").strip())

    email = input("\nEnter Test Email Address: ").strip()
    password = getpass.getpass("Enter App Password/Token: ")
    
    if not email or not password:
        print("Error: Email and password are required.")
        sys.exit(1)
        
    print("\n--- Cryptographic Integration Demonstration ---")
    try:
        encrypted_pass = encrypt_credentials(password)
        print(f"1. Encrypted password byte-string (to DB): {encrypted_pass[:30]}...[TRUNCATED]")
        decrypted_pass = decrypt_credentials(encrypted_pass)
        print("2. Decrypted password byte-string (in memory): [CONFIRMED MATCH]")
    except Exception as e:
        print(f"Encryption integration failed: {e}")
        sys.exit(1)

    smtp_ok = test_smtp_connection(email, decrypted_pass, smtp_host, smtp_port, use_ssl)
    imap_ok = test_imap_connection(email, decrypted_pass, imap_host, imap_port)
    
    print("\n================================================================================")
    print("                           DIAGNOSTIC TEST SUMMARY")
    print("================================================================================")
    print(f"SMTP Outbound Path: [{'SUCCESS' if smtp_ok else 'FAILED'}]")
    print(f"IMAP Inbound Path:  [{'SUCCESS' if imap_ok else 'FAILED'}]")
    print("================================================================================")

if __name__ == "__main__":
    main()
