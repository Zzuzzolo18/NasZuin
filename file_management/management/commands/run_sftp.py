import socket
import threading
import sys
import time
import os
import paramiko
from django.core.management.base import BaseCommand
from django.conf import settings
from file_management.models import StorageTier
from file_management.sftp_server import ChrootedSFTPServer
from pathlib import Path
from django.contrib.auth import authenticate

import logging
from django.db import close_old_connections

# paramiko.util.log_to_file sets up the root logger effectively for paramiko
# But we need to ensure our custom logs go there too.
# The best way is to use 'paramiko.transport' logger which is what log_to_file configures handlers for?
# Actually log_to_file configures the 'paramiko' logger.
logger = logging.getLogger("paramiko.transport")

class DjangoSSHInterface(paramiko.ServerInterface):
    def __init__(self, client_ip):
        self.client_ip = client_ip
        self.user = None
        self.user_home = None

    def check_channel_request(self, kind, chanid):
        logger.info(f"DEBUG: check_channel_request kind={kind} chanid={chanid}")
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED



    def check_channel_shell_request(self, channel):
        print(f"DEBUG: check_channel_shell_request channel={channel}", flush=True)
        # Allow shell but maybe do nothing or launch simple shell?
        # For SFTP only servers, usually we deny shell unless we implement one.
        # But some clients try shell first.
        return False

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        print(f"DEBUG: check_channel_pty_request term={term}", flush=True)
        return True
        
    def check_channel_exec_request(self, channel, command):
        print(f"DEBUG: check_channel_exec_request command={command}", flush=True)
        return False


    def check_auth_interactive(self, username, submethods):
        print(f"DEBUG: check_auth_interactive entry for {username}", flush=True)
        # We can implement this by asking for password, but usually password auth is enough.
        # Returning paramiko.AUTH_FAILED will make client try password.
        return paramiko.AUTH_FAILED

    def check_auth_password(self, username, password):
        print(f"DEBUG: check_auth_password entry for {username}", flush=True)
        
        # AxesBackend requires a request object to track IP addresses
        from django.http import HttpRequest
        request = HttpRequest()
        request.META['REMOTE_ADDR'] = self.client_ip
        
        close_old_connections()
        try:
            print(f"DEBUG: Attempting auth for {username}...", flush=True)
            # Pass request to authenticate for Axes compatibility
            user = authenticate(request=request, username=username, password=password)
            if user is not None:
                self.user = user
                
                # Resolve user home directory immediately after auth
                # so it's available when the SFTP subsystem handler fires
                try:
                    hot_tier = StorageTier.objects.first()
                    if hot_tier:
                        user_home = Path(hot_tier.mount_point) / user.username
                        if not user_home.exists():
                            user_home.mkdir(parents=True, exist_ok=True)
                        self.user_home = str(user_home)
                        print(f"DEBUG: User home set to {self.user_home}", flush=True)
                    else:
                        print("WARNING: No StorageTier configured, SFTP will use cwd", flush=True)
                except Exception as e:
                    print(f"WARNING: Could not resolve user home: {e}", flush=True)
                
                print(f"DEBUG: Auth succeeded for {username}", flush=True)
                return paramiko.AUTH_SUCCESSFUL
        except Exception as e:
            print(f"DEBUG: Auth error for {username}: {e}", flush=True)
        finally:
            close_old_connections()
            
        print(f"DEBUG: Auth failed for {username}", flush=True)
        return paramiko.AUTH_FAILED
    
    def get_allowed_auths(self, username):
        return 'password,keyboard-interactive'

class DebugSFTPServer(paramiko.SFTPServer):
    def run(self):
        print("DEBUG: DebugSFTPServer thread started (run method)", flush=True)
        try:
            super().run()
        except Exception as e:
            print(f"CRITICAL: DebugSFTPServer thread crashed: {e}", flush=True)
            import traceback
            traceback.print_exc()
        finally:
            print("DEBUG: DebugSFTPServer thread ended", flush=True)

class Command(BaseCommand):
    help = 'Runs a Python-based SFTP Server'

    def add_arguments(self, parser):
        parser.add_argument('--port', type=int, default=2222)
        parser.add_argument('--host', type=str, default='0.0.0.0')
        parser.add_argument('--keyfile', type=str, default='host.key')

    def handle(self, *args, **options):
        # Paramiko logging - Manual setup to avoid Django formatter crash
        log_path = os.path.join(settings.BASE_DIR, 'paramiko.log')
        plogger = logging.getLogger("paramiko")
        plogger.setLevel(logging.DEBUG)
        plogger.propagate = False # CRITICAL: Stop logs from hitting Django's root logger which crashes!
        
        # Clear existing handlers to avoid duplicates or bad formatters
        if plogger.hasHandlers():
            plogger.handlers.clear()
            
        fh = logging.FileHandler(log_path)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        plogger.addHandler(fh)
        
        # Ensure transport logger is also captured if separate (it usually is under paramiko, but just in case)
        tlogger = logging.getLogger("paramiko.transport")
        tlogger.propagate = False
        if not tlogger.hasHandlers():
            tlogger.addHandler(fh)
            tlogger.setLevel(logging.DEBUG)

        # Ensure sftp logger is also captured 
        slogger = logging.getLogger("paramiko.sftp")
        slogger.propagate = False
        if not slogger.hasHandlers():
            slogger.addHandler(fh)
            slogger.setLevel(logging.DEBUG)

        host = options['host']
        port = options['port']
        keyfile = options['keyfile']

        if not os.path.exists(keyfile):
            print(f"Generating keyfile {keyfile}", flush=True)
            key = paramiko.RSAKey.generate(2048)
            key.write_private_key_file(keyfile)
        
        try:
            print(f"Loading host key from {keyfile}", flush=True)
            host_key = paramiko.RSAKey(filename=keyfile)
        except Exception as e:
            print(f"Error loading host key: {e}", flush=True)
            return

        print(f"Starting Manual Threaded SFTP Server on {host}:{port}", flush=True)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            sock.listen(10)
            
            while True:
                client, addr = sock.accept()
                print(f"Connection from {addr}", flush=True)
                t = threading.Thread(target=self.handle_client, args=(client, host_key))
                t.daemon = True
                t.start()
                
        except Exception as e:
            print(f"Server crashed: {e}", flush=True)
            sys.exit(1)

    def handle_client(self, client_sock, host_key):
        transport = paramiko.Transport(client_sock)
        try:
            # Compatibility Tweaks (Optional - let's keep them if they help mobile)
            transport.packetizer.REKEY_BYTES = pow(2, 40)
            transport.packetizer.REKEY_PACKETS = pow(2, 40)
            transport.local_version = 'SSH-2.0-OpenSSH_8.2p1'
            
            transport.add_server_key(host_key)
            
            # Register SFTP subsystem handler BEFORE starting the server
            # Paramiko will internally handle the subsystem request and
            # instantiate ChrootedSFTPServer, passing the ServerInterface as 'server'
            transport.set_subsystem_handler('sftp', paramiko.SFTPServer, ChrootedSFTPServer)
            
            # Get IP
            try:
                client_ip = client_sock.getpeername()[0]
            except Exception:
                client_ip = '0.0.0.0'

            server = DjangoSSHInterface(client_ip=client_ip)
            
            print("Starting server negotiation...", flush=True)
            try:
                transport.start_server(server=server)
                print("Server negotiation started.", flush=True)
            except Exception as e:
                print(f"SSH Negotiation Failed (Exception): {e}", flush=True)
                return

            # Loop to handle channels - but SFTPServer init is now in callback
            while transport.is_active():
                channel = transport.accept(1.0)
                if channel is None:
                    continue
                
                # We just accept the channel. The subsystem request will follow
                # and trigger check_channel_subsystem_request where we start the SFTP functionality.
                print(f"Channel accepted: {channel.get_id()} (Waiting for subsystem request)", flush=True)
            
            # Keep alive check is now implicit in the while loop + accept timeout
                
        except Exception as e:
            print(f"Connection Error: {e}", flush=True)
        finally:
            print("Closing transport", flush=True)
            transport.close()
