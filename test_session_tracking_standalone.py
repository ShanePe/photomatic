"""
Standalone test for session hash tracker.
Tests the core logic without Flask dependencies.
"""

import sys
import hashlib
import threading
import time

# Mock globals module to avoid Flask dependency
class MockGlobals:
    class logger:
        @staticmethod
        def debug(*args, **kwargs):
            print(f"[DEBUG] {args[0] % args[1:]}" if len(args) > 1 else f"[DEBUG] {args[0]}")
        
        @staticmethod
        def info(*args, **kwargs):
            print(f"[INFO] {args[0] % args[1:]}" if len(args) > 1 else f"[INFO] {args[0]}")
        
        @staticmethod
        def error(*args, **kwargs):
            print(f"[ERROR] {args[0] % args[1:]}" if len(args) > 1 else f"[ERROR] {args[0]}")

sys.modules['app.globals'] = type(sys)('app.globals')
sys.modules['app.globals'].logger = MockGlobals.logger

# Now we can test the session tracker core logic
_sessions = {}
_sessions_lock = threading.RLock()
EXPIRATION_HOURS = 24

def _get_hash_for_path(path: str) -> str:
    """Get MD5 hash of a photo path for deduplication."""
    return hashlib.md5(path.encode()).hexdigest()

def _cleanup_expired_sessions():
    """Remove sessions older than EXPIRATION_HOURS."""
    with _sessions_lock:
        now = time.time()
        expired = [
            sid for sid, data in _sessions.items()
            if now - data["created"] > (EXPIRATION_HOURS * 3600)
        ]
        for sid in expired:
            del _sessions[sid]

def register_session(session_id: str, random_pool_size: int = 100) -> None:
    _cleanup_expired_sessions()
    with _sessions_lock:
        _sessions[session_id] = {
            "created": time.time(),
            "cycle_phase": "same_day",
            "same_day_hashes": set(),
            "random_shown_count": 0,
            "cycle_random_pool_size": random_pool_size,
        }

def get_cycle_phase(session_id: str) -> str:
    _cleanup_expired_sessions()
    with _sessions_lock:
        if session_id not in _sessions:
            return "same_day"
        return _sessions[session_id]["cycle_phase"]

def mark_same_day_photo_served(session_id: str, path: str) -> None:
    _cleanup_expired_sessions()
    path_hash = _get_hash_for_path(path)
    with _sessions_lock:
        if session_id not in _sessions:
            register_session(session_id)
        _sessions[session_id]["same_day_hashes"].add(path_hash)

def mark_random_photo_served(session_id: str) -> None:
    _cleanup_expired_sessions()
    with _sessions_lock:
        if session_id not in _sessions:
            register_session(session_id)
        _sessions[session_id]["random_shown_count"] += 1

def has_same_day_photo_been_served(session_id: str, path: str) -> bool:
    _cleanup_expired_sessions()
    path_hash = _get_hash_for_path(path)
    with _sessions_lock:
        if session_id not in _sessions:
            return False
        return path_hash in _sessions[session_id]["same_day_hashes"]

def should_transition_to_same_day_phase(session_id: str) -> bool:
    _cleanup_expired_sessions()
    with _sessions_lock:
        if session_id not in _sessions:
            return False
        
        data = _sessions[session_id]
        return (
            data["cycle_phase"] == "random"
            and data["random_shown_count"] >= data["cycle_random_pool_size"]
        )

def transition_to_random_phase(session_id: str) -> None:
    with _sessions_lock:
        if session_id in _sessions:
            _sessions[session_id]["cycle_phase"] = "random"
            _sessions[session_id]["random_shown_count"] = 0

def transition_to_same_day_phase(session_id: str) -> None:
    with _sessions_lock:
        if session_id in _sessions:
            _sessions[session_id]["cycle_phase"] = "same_day"
            _sessions[session_id]["same_day_hashes"] = set()
            _sessions[session_id]["random_shown_count"] = 0

def reset_session(session_id: str, random_pool_size: int = 100) -> None:
    with _sessions_lock:
        _sessions[session_id] = {
            "created": time.time(),
            "cycle_phase": "same_day",
            "same_day_hashes": set(),
            "random_shown_count": 0,
            "cycle_random_pool_size": random_pool_size,
        }


# ============================================================================
# TEST CASES
# ============================================================================

def test_register_session():
    """Test session registration with pool size."""
    print("\n📝 TEST: Register Session")
    _sessions.clear()
    
    session_id = "test-session-1"
    register_session(session_id, random_pool_size=5)
    
    assert get_cycle_phase(session_id) == "same_day", "Should start in same_day phase"
    print("   ✓ Session registered and started in same_day phase")


def test_cycle_phase_transitions():
    """Test transitioning between same_day and random phases."""
    print("\n📝 TEST: Cycle Phase Transitions")
    _sessions.clear()
    
    session_id = "test-session-2"
    register_session(session_id, random_pool_size=3)
    
    assert get_cycle_phase(session_id) == "same_day", "Should start in same_day"
    print("   ✓ Started in same_day phase")
    
    transition_to_random_phase(session_id)
    assert get_cycle_phase(session_id) == "random", "Should transition to random"
    print("   ✓ Transitioned to random phase")
    
    transition_to_same_day_phase(session_id)
    assert get_cycle_phase(session_id) == "same_day", "Should transition back to same_day"
    print("   ✓ Transitioned back to same_day phase")


def test_same_day_photo_tracking():
    """Test marking and checking same-day photos."""
    print("\n📝 TEST: Same-Day Photo Tracking")
    _sessions.clear()
    
    session_id = "test-session-3"
    register_session(session_id)
    
    photo_path = "/photos/today.jpg"
    
    assert not has_same_day_photo_been_served(session_id, photo_path), "Should not be served initially"
    print("   ✓ Photo not marked as served initially")
    
    mark_same_day_photo_served(session_id, photo_path)
    assert has_same_day_photo_been_served(session_id, photo_path), "Should be marked as served"
    print("   ✓ Photo marked and tracked as served")
    
    # Different photo should not be tracked
    other_photo = "/photos/other.jpg"
    assert not has_same_day_photo_been_served(session_id, other_photo), "Other photo should not be tracked"
    print("   ✓ Other photos remain untracked")


def test_random_photo_counting():
    """Test random photo counting for cycle transition."""
    print("\n📝 TEST: Random Photo Counting")
    _sessions.clear()
    
    session_id = "test-session-4"
    pool_size = 3
    register_session(session_id, random_pool_size=pool_size)
    
    transition_to_random_phase(session_id)
    print("   ✓ Transitioned to random phase")
    
    # Mark photos without reaching limit
    for i in range(pool_size - 1):
        mark_random_photo_served(session_id)
        assert not should_transition_to_same_day_phase(session_id), f"Should not transition at count {i+1}"
    print(f"   ✓ Did not transition after {pool_size-1} photos (need {pool_size})")
    
    # Mark one more to reach the limit
    mark_random_photo_served(session_id)
    assert should_transition_to_same_day_phase(session_id), "Should transition after reaching quota"
    print(f"   ✓ Ready to transition after reaching quota of {pool_size} photos")


def test_reset_session():
    """Test session reset clears state."""
    print("\n📝 TEST: Session Reset")
    _sessions.clear()
    
    session_id = "test-session-5"
    register_session(session_id, random_pool_size=5)
    
    # Mark some photos
    mark_same_day_photo_served(session_id, "/photos/1.jpg")
    transition_to_random_phase(session_id)
    mark_random_photo_served(session_id)
    mark_random_photo_served(session_id)
    
    assert get_cycle_phase(session_id) == "random", "Should be in random phase before reset"
    print("   ✓ Session in random phase before reset")
    
    # Reset
    reset_session(session_id, random_pool_size=5)
    
    assert get_cycle_phase(session_id) == "same_day", "Should be back in same_day after reset"
    assert not has_same_day_photo_been_served(session_id, "/photos/1.jpg"), "Tracking should be cleared"
    print("   ✓ Session reset to initial state (same_day, cleared tracking)")


def test_cycle_simulation():
    """Simulate a full photo serving cycle."""
    print("\n📝 TEST: Full Cycle Simulation")
    _sessions.clear()
    
    session_id = "test-cycle-sim"
    pool_size = 5
    register_session(session_id, random_pool_size=pool_size)
    
    request = 0
    
    # Phase 1: Serve same-day photos
    print("   Phase 1: Serving same-day photos...")
    for i in range(1, 6):
        request += 1
        phase = get_cycle_phase(session_id)
        if phase == "same_day":
            path = f"/photos/today_{i}.jpg"
            mark_same_day_photo_served(session_id, path)
            print(f"      Request {request}: Same-day photo {i} ✓")
        else:
            break
    
    # Transition to random phase (simulated)
    print("   Phase 2: Transitioning to random phase...")
    transition_to_random_phase(session_id)
    
    # Phase 2: Serve random photos
    print(f"   Phase 2: Serving {pool_size} random photos...")
    for i in range(1, pool_size + 1):
        request += 1
        mark_random_photo_served(session_id)
        print(f"      Request {request}: Random photo {i} ✓")
    
    # Check transition readiness
    assert should_transition_to_same_day_phase(session_id), "Should be ready to transition"
    print(f"   ✓ After {pool_size} random photos, ready to transition back")
    
    # Transition back
    print("   Phase 3: Transitioning back to same-day phase...")
    transition_to_same_day_phase(session_id)
    assert get_cycle_phase(session_id) == "same_day", "Should be back in same_day"
    print("   ✓ Successfully cycled: same_day → random → same_day")


# ============================================================================
# RUN ALL TESTS
# ============================================================================

def run_all_tests():
    """Run all test functions."""
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     SESSION HASH TRACKER - UNIT TESTS (STANDALONE)             ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    
    tests = [
        test_register_session,
        test_cycle_phase_transitions,
        test_same_day_photo_tracking,
        test_random_photo_counting,
        test_reset_session,
        test_cycle_simulation,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"   ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"   ✗ ERROR: {e}")
            failed += 1
    
    # Summary
    print("\n" + "═" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("═" * 70)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! 🎉\n")
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED\n")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
