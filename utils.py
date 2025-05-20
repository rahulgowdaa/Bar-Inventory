from models import db, UserActionLog

def log_action(user_id, action):
    if user_id is not None:
        log_entry = UserActionLog(user_id=user_id, action=action)
        db.session.add(log_entry)
        db.session.commit()
    else:
        print("Error: user_id is None, cannot log action.") 