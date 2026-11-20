"""Tests for session hash tracking with cycle-based photo serving."""

import time
from app.session_hash_tracker import (
    get_cycle_phase,
    has_same_day_photo_been_served,
    mark_random_photo_served,
    mark_same_day_photo_served,
    register_session,
    reset_session,
    should_transition_to_random_phase,
    should_transition_to_same_day_phase,
    transition_to_random_phase,
    transition_to_same_day_phase,
)


def test_register_session():
    """Test session registration with pool size."""
    session_id = "test-session-1"
    register_session(session_id, random_pool_size=5)
    
    # Should start in same_day phase
    assert get_cycle_phase(session_id) == "same_day"


def test_cycle_phase_transitions():
    """Test transitioning between same_day and random phases."""
    session_id = "test-session-2"
    register_session(session_id, random_pool_size=3)
    
    # Start in same_day
    assert get_cycle_phase(session_id) == "same_day"
    
    # Transition to random
    transition_to_random_phase(session_id)
    assert get_cycle_phase(session_id) == "random"
    
    # Transition back to same_day
    transition_to_same_day_phase(session_id)
    assert get_cycle_phase(session_id) == "same_day"


def test_same_day_photo_tracking():
    """Test marking and checking same-day photos."""
    session_id = "test-session-3"
    register_session(session_id)
    
    photo_path = "/photos/today.jpg"
    
    # Initially not served
    assert not has_same_day_photo_been_served(session_id, photo_path)
    
    # Mark as served
    mark_same_day_photo_served(session_id, photo_path)
    
    # Now should be served
    assert has_same_day_photo_been_served(session_id, photo_path)


def test_random_photo_counting():
    """Test random photo counting for cycle transition."""
    session_id = "test-session-4"
    pool_size = 3
    register_session(session_id, random_pool_size=pool_size)
    
    # Transition to random phase
    transition_to_random_phase(session_id)
    
    # Mark random photos
    for i in range(pool_size - 1):
        mark_random_photo_served(session_id)
        # Not yet ready to transition
        assert not should_transition_to_same_day_phase(session_id)
    
    # Mark one more to reach the limit
    mark_random_photo_served(session_id)
    # Now should be ready to transition
    assert should_transition_to_same_day_phase(session_id)


def test_reset_session():
    """Test session reset clears state."""
    session_id = "test-session-5"
    register_session(session_id, random_pool_size=5)
    
    # Mark some photos
    mark_same_day_photo_served(session_id, "/photos/1.jpg")
    transition_to_random_phase(session_id)
    mark_random_photo_served(session_id)
    mark_random_photo_served(session_id)
    
    # Reset
    reset_session(session_id, random_pool_size=5)
    
    # Should be back in same_day phase with no tracked photos
    assert get_cycle_phase(session_id) == "same_day"
    assert not has_same_day_photo_been_served(session_id, "/photos/1.jpg")


if __name__ == "__main__":
    test_register_session()
    test_cycle_phase_transitions()
    test_same_day_photo_tracking()
    test_random_photo_counting()
    test_reset_session()
    print("All tests passed!")
