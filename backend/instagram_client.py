import os
import time
import random
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword, TwoFactorRequired, LoginRequired,
    RateLimitError, ChallengeRequired, ClientError # Removed ClientLoginError, added ClientError
)
from .logger import log_message # Use relative import

# In-memory storage for the Instagram client instance and session data
# NOTE: This will be reset if the server restarts on Render free tier.
ig_client: Client = None
session_data = {}

def get_client():
    """Returns the current Instagram client instance."""
    global ig_client
    return ig_client

def login(username, password):
    """Attempts to log in to Instagram."""
    global ig_client, session_data
    log_message('info', f"Attempting to log in as {username}...")

    # Initialize client
    ig_client = Client()

    # Load session data if available (basic in-memory approach)
    # A more robust solution would save/load this to a file or DB, but
    # the request specifies no external DB and Render free tier ephemeral storage.
    # This in-memory approach will likely fail on server restarts.
    if session_data:
        try:
            log_message('info', "Attempting to load session data...")
            ig_client.set_settings(session_data)
            # Use login_by_sessionid or similar if session data is loaded correctly
            # However, login() with username/password after set_settings can also
            # validate the session and potentially refresh it. Let's stick to login()
            # for simplicity, assuming set_settings primes it.
            ig_client.login(username, password)
            log_message('info', f"Successfully logged in using session data as {username}")
            return {"status": "success", "message": "Logged in successfully."}
        except (LoginRequired, ClientError, BadPassword): # Catch ClientError here
            log_message('warning', "Session data invalid or expired or general client error during session login. Attempting fresh login.")
            session_data = {} # Clear invalid session data
        except Exception as e:
            log_message('error', f"Error loading or using session data: {e}")
            session_data = {} # Clear invalid session data


    try:
        # Attempt fresh login
        ig_client.login(username, password)
        log_message('info', f"Successfully logged in as {username}")
        # Save session data (in-memory)
        session_data = ig_client.get_settings()
        return {"status": "success", "message": "Logged in successfully."}

    except BadPassword:
        log_message('error', "Login failed: Incorrect password.")
        ig_client = None # Clear client on failure
        session_data = {}
        return {"status": "error", "message": "Incorrect password."}
    except TwoFactorRequired as e:
        log_message('warning', "Login requires 2FA.")
        # Store verification code data temporarily
        session_data['2fa_code_data'] = e.dict()
        # Store username and password temporarily for 2FA completion if needed
        session_data['temp_username'] = username
        session_data['temp_password'] = password
        return {"status": "2fa_required", "message": "2FA required. Check your email/phone for the code."}
    except ChallengeRequired:
         log_message('warning', "Login requires challenge (e.g., email/phone verification link).")
         # instagrapi might handle this automatically or require manual intervention.
         # For this simple bot, we'll just report it.
         ig_client = None # Clear client on failure
         session_data = {}
         return {"status": "challenge_required", "message": "Challenge required. Please try logging in manually on Instagram first or check email/phone."}
    except ClientError as e: # Catch general client errors during fresh login
        log_message('error', f"A client error occurred during login: {e}")
        ig_client = None # Clear client on failure
        session_data = {}
        return {"status": "error", "message": f"Login failed due to client error: {e}"}
    except Exception as e:
        log_message('error', f"An unexpected error occurred during login: {e}")
        ig_client = None # Clear client on failure
        session_data = {}
        return {"status": "error", "message": f"Login failed: {e}"}

def complete_2fa(verification_code):
    """Completes the 2FA login process."""
    global ig_client, session_data
    # Ensure client is initialized and 2FA data is present
    if not ig_client or '2fa_code_data' not in session_data or 'temp_username' not in session_data or 'temp_password' not in session_data:
        log_message('error', "2FA completion failed: Client not initialized, 2FA data missing, or temporary credentials missing.")
        return {"status": "error", "message": "2FA process not initiated correctly. Please try logging in again."}

    try:
        log_message('info', f"Attempting to complete 2FA with code: {verification_code}")
        # Use the verification_code_data and temporary credentials stored during the initial login attempt
        ig_client.complete_login(session_data['temp_username'], session_data['temp_password'], verification_code, session_data['2fa_code_data'])
        log_message('info', "2FA successfully completed.")
        # Save the new session data after successful 2FA
        session_data = ig_client.get_settings()
        # Clean up temporary 2FA data and credentials
        if '2fa_code_data' in session_data:
             del session_data['2fa_code_data']
        if 'temp_username' in session_data:
             del session_data['temp_username']
        if 'temp_password' in session_data:
             del session_data['temp_password']

        return {"status": "success", "message": "Logged in successfully after 2FA."}
    except BadPassword: # Can happen if 2FA code is wrong
        log_message('error', "2FA completion failed: Incorrect 2FA code.")
        ig_client = None # Clear client on failure
        session_data = {} # Clear session data including temp credentials
        return {"status": "error", "message": "Incorrect 2FA code."}
    except ClientError as e: # Catch general client errors during 2FA completion
        log_message('error', f"A client error occurred during 2FA completion: {e}")
        ig_client = None # Clear client on failure
        session_data = {} # Clear session data including temp credentials
        return {"status": "error", "message": f"2FA completion failed due to client error: {e}"}
    except Exception as e:
        log_message('error', f"An unexpected error occurred during 2FA completion: {e}")
        ig_client = None # Clear client on failure
        session_data = {} # Clear session data including temp credentials
        return {"status": "error", "message": f"2FA completion failed: {e}"}


def get_user_id(username):
    """Gets the user ID for a given username."""
    client = get_client()
    if not client or not client.is_logged_in: # Added check for is_logged_in
        log_message('error', "Client not initialized or not logged in. Cannot get user ID.")
        return None
    try:
        log_message('info', f"Fetching user ID for {username}...")
        user = client.user_info_by_username(username)
        log_message('info', f"Found user ID: {user.pk} for {username}")
        return user.pk
    except Exception as e:
        log_message('error', f"Failed to get user ID for {username}: {e}")
        return None

def get_followers_or_following(user_id, list_type):
    """Fetches followers or following list for a user ID."""
    client = get_client()
    if not client or not client.is_logged_in: # Added check for is_logged_in
        log_message('error', "Client not initialized or not logged in. Cannot fetch list.")
        return {"status": "error", "message": "Not logged in."}

    try:
        log_message('info', f"Fetching {list_type} for user ID: {user_id}")
        users = []
        # Use a generator to fetch users in batches
        # instagrapi v1.19.2 uses user_followers_v1_chunk and user_following_v1_chunk
        if list_type == 'followers':
            # The chunk methods return generators
            for follower in client.user_followers_v1_chunk(user_id):
                 users.append({"pk": follower.pk, "username": follower.username, "full_name": follower.full_name})
                 # log_message('info', f"Fetched {len(users)} followers so far...") # Log less frequently for large lists

        elif list_type == 'following':
            # The chunk methods return generators
            for following in client.user_following_v1_chunk(user_id):
                users.append({"pk": following.pk, "username": following.username, "full_name": following.full_name})
                # log_message('info', f"Fetched {len(users)} following so far...") # Log less frequently for large lists
        else:
             return {"status": "error", "message": f"Invalid list type: {list_type}. Must be 'followers' or 'following'."}


        log_message('info', f"Successfully fetched {len(users)} {list_type}.")
        return {"status": "success", "users": users}

    except RateLimitError:
        log_message('warning', "Rate limit hit while fetching list. Wait a bit before trying again.")
        return {"status": "warning", "message": "Rate limit hit. Please wait before fetching another list."}
    except ClientError as e: # Catch general client errors during list fetching
        log_message('error', f"A client error occurred while fetching {list_type} for user ID {user_id}: {e}")
        return {"status": "error", "message": f"Failed to fetch list due to client error: {e}"}
    except Exception as e:
        log_message('error', f"Failed to fetch {list_type} for user ID {user_id}: {e}")
        return {"status": "error", "message": f"Failed to fetch list: {e}"}

def send_mass_dm(recipient_pks, message, min_delay, max_delay, max_recipients):
    """Sends a direct message to a list of user PKS with delays."""
    client = get_client()
    if not client or not client.is_logged_in: # Added check for is_logged_in
        log_message('error', "Client not initialized or not logged in. Cannot send messages.")
        return {"status": "error", "message": "Not logged in."}

    log_message('info', f"Attempting to send message to {min(len(recipient_pks), max_recipients)} recipients.")
    sent_count = 0
    failed_count = 0
    errors = []

    # Shuffle recipients to make it less sequential
    random.shuffle(recipient_pks)

    # Limit the number of recipients to the specified maximum
    recipients_to_process = recipient_pks[:max_recipients]

    for i, pk in enumerate(recipients_to_process):
        delay = random.randint(min_delay, max_delay)
        log_message('info', f"Sending message to user PK: {pk} (Recipient {i+1}/{len(recipients_to_process)})...")

        try:
            # instagrapi expects a list of recipient PKS for a single thread,
            # or a single PK to create a new thread. For mass DM, we send
            # to each recipient individually, potentially creating new threads.
            # This is generally safer than adding many users to one thread.
            client.direct_send(message, user_ids=[pk])
            log_message('info', f"Successfully sent message to {pk}.")
            sent_count += 1
        except RateLimitError:
            log_message('warning', f"Rate limit hit while sending to {pk}. Waiting longer.")
            failed_count += 1
            errors.append(f"Rate limit hit for {pk}")
            # Wait for a longer period if rate limited
            time.sleep(max(delay * 2, 60)) # Wait at least 60 seconds
            continue # Try the next recipient after waiting
        except ClientError as e: # Catch general client errors during sending
            log_message('error', f"A client error occurred while sending to {pk}: {e}")
            failed_count += 1
            errors.append(f"Failed to send to {pk} due to client error: {e}")
        except Exception as e:
            log_message('error', f"Failed to send message to {pk}: {e}")
            failed_count += 1
            errors.append(f"Failed to send to {pk}: {e}")

        # Only wait if there are more messages to send within the limit
        if i < len(recipients_to_process) - 1:
             log_message('info', f"Waiting for {delay} seconds before sending the next message...")
             time.sleep(delay)

    log_message('info', f"Mass DM process finished. Sent: {sent_count}, Failed: {failed_count}.")
    return {"status": "completed", "sent_count": sent_count, "failed_count": failed_count, "errors": errors}

# Basic function to check if the client is logged in
def is_logged_in():
    """Checks if the Instagram client is currently logged in."""
    global ig_client
    # instagrapi client has an `is_logged_in` method
    return ig_client is not None and ig_client.is_logged_in

