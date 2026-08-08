from functools import wraps

from flask import abort, g, session
from flask_login import current_user

from . import db
from .models import Membership, Organization


def tenant_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        org_id = session.get("organization_id")
        membership = db.session.execute(
            db.select(Membership).where(
                Membership.user_id == current_user.id,
                Membership.organization_id == org_id,
            )
        ).scalar_one_or_none()
        if not membership:
            membership = db.session.execute(
                db.select(Membership).where(Membership.user_id == current_user.id).order_by(Membership.id)
            ).scalars().first()
            if not membership:
                abort(403)
            session["organization_id"] = membership.organization_id
        g.membership = membership
        g.organization = db.session.get(Organization, membership.organization_id)
        return view(*args, **kwargs)
    return wrapped

