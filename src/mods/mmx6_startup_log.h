#pragma once
#ifdef __cplusplus
extern "C" {
#endif
/* Host-only diagnostics, active before the launcher or guest boot. NULL uses
 * the executable/AppImage folder; a root argument is for standalone fixtures. */
int mmx6_startup_log_begin(const char *root);
const char *mmx6_startup_log_path(void);
void mmx6_startup_log_end(void);
#ifdef __cplusplus
}
#endif
