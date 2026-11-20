# Kept empty on purpose: extensions.py imports models/base.py, and importing the models here would
# import extensions.py again before `db` exists (circular import). app/__init__.py imports every model.
