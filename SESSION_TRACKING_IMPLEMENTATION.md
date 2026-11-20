"""
PHOTOMATIC PHOTO INDEX TRACKING - IMPLEMENTATION SUMMARY

PROBLEM:
--------
Some clients kept rotating the first photo instead of cycling through the full photo library.
The root cause was that photo_index and photo_served were read but never incremented,
so the cookie never updated, and clients couldn't track which photos had been shown.

SOLUTION: Option 3 - Session Hash-Based Tracking with Cycling
==============================================================

This implementation replaces simple index tracking with a robust server-side session
tracking system that:

1. Generates a unique session_id per browser (UUID, stored in cookie)
2. Implements a cycle-based serving pattern:
   - Phase 1: Serve all same-day photos sequentially (no duplicates within cycle)
   - Phase 2: Serve N random photos (N = cache.same_day_cycle from config, default: 100)
   - Repeat forever

3. Tracks served photos via MD5 hash of the file path
4. Auto-expires sessions after 24 hours
5. Handles smooth transitions between same-day and random phases

FILES CREATED/MODIFIED:
=======================

NEW: app/session_hash_tracker.py
  - Core tracking logic with thread-safe session management
  - Functions for phase transitions, photo tracking, and session lifecycle
  - Automatic cleanup of expired sessions
  
  Key functions:
  - register_session(session_id, random_pool_size)
  - get_cycle_phase(session_id) -> "same_day" | "random"
  - mark_same_day_photo_served(session_id, path)
  - mark_random_photo_served(session_id)
  - has_same_day_photo_been_served(session_id, path)
  - should_transition_to_random_phase(session_id)
  - should_transition_to_same_day_phase(session_id)
  - transition_to_random_phase(session_id)
  - transition_to_same_day_phase(session_id)
  - reset_session(session_id, random_pool_size)

MODIFIED: app/session.py
  - Added session_id to default_photo_state()
  - Session ID is generated as UUID on first visit
  - Session ID persists in the browser cookie
  - Maintains backward compatibility with existing photo_index/photo_served fields

MODIFIED: app/routes.py
  - Updated /random endpoint with cycle-based logic
  - Updated /api/random endpoint with cycle-based logic
  - Updated /clear_cache endpoint to reset session tracking
  
  New serving flow:
  1. Get session_id from photo state
  2. Register session with configured pool_size
  3. Check current cycle phase (same_day or random)
  4. If same_day:
     - Try to get a same-day photo
     - If it's new, mark as served and return it
     - If already served, transition to random phase
     - If no same-day photos, transition to random phase
  5. If random:
     - Check if we've served enough random photos
     - If yes, transition back to same_day phase
     - If no, serve a random photo and increment counter
  6. Persist photo state with updated session info

NEW: tests/test_session_hash_tracker.py
  - Unit tests for session tracking logic
  - Tests for phase transitions
  - Tests for photo tracking
  - Tests for cycle counting

CONFIGURATION:
===============
The cycle behavior uses existing config: cache.same_day_cycle (default: 100)

Example config.yaml:
  cache:
    limit_enabled: false
    limit: 2000
    same_day_cycle: 100     # Show 100 random photos per cycle

To change the ratio of same-day to random photos, adjust same_day_cycle in config.

HOW IT WORKS - EXAMPLE:
=======================
Browser visits with 5 same-day photos and 1000 total photos in library:

Request 1-5:   Show same-day photo 1-5 (marked as served in session)
Request 6:     All same-day photos served → transition to random phase
Request 6-105: Show 100 random photos (counter increments from 1-100)
Request 106:   Random photo count reached 100 → transition back to same_day phase
Request 107:   Reset same-day tracking, start showing same-day photos again (1-5)
Request 108-207: Show 100 random photos again
... repeats forever

BENEFITS:
=========
✓ No index/counter overflow issues
✓ Handles browser reloads gracefully (session persists via cookie)
✓ Works across multiple browser tabs (each gets its own session)
✓ Auto-expires old sessions (24-hour window)
✓ Thread-safe with RLock protection
✓ Prevents duplicate photos within a same-day cycle
✓ Ensures today's photos appear regularly
✓ Configurable ratio of same-day to random photos
✓ Backward compatible with existing photo_index/photo_served fields

TESTING:
========
Run existing tests:
  pytest tests/test_session_hash_tracker.py

Run all tests:
  pytest tests/

Verify photo serving:
  1. Load http://localhost:80/
  2. Watch photos cycle through
  3. Check browser console logs for phase transitions
  4. Check server logs: [SessionHashTracker] messages
  5. Refresh page - should continue from same session
  6. Open in new incognito window - should get new session

EDGE CASES HANDLED:
===================
✓ No same-day photos: Skips to random phase immediately
✓ Fewer same-day photos than random pool size: Works seamlessly
✓ Single photo in library: Shows same photo, cycles to random (all random), cycles back
✓ Empty library: Returns 404 as before
✓ Cache rebuild during serving: Returns 503 as before
✓ Manual cache clear: Resets session tracking
✓ Browser with old session cookie: Creates new session on next request
✓ Session expires after 24 hours: Automatic cleanup, fresh start
"""
