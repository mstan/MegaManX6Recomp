# Startup error logs

If the launcher cannot sign in, join a session or start the game, open
`startup-log-location.txt` beside the executable. It names the current log in
`saves/diagnostics/startup-<time>-<process>.log`.

Logging starts before the launcher and before gameplay recording. It works
when the game is opened without a console window. An existing console or
redirected error stream keeps receiving the same messages.

Attach that log when reporting a startup problem. A gameplay input recording
is a separate file and might not exist if startup failed. If the log cannot be
created, the location file reports that failure instead of pointing to an old
log. Keep the executable folder writable so the game can create these files.
