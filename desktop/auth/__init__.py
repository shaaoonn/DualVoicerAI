"""Authentication and single-instance enforcement.

Pure HTTP and OS-level primitives — no Tk dependencies — so they can be
unit-tested without spinning up the GUI. The thin mixin wrapper
(``auth.auth_panel.AuthPanelMixin``) handles the UI side.
"""
