#ifndef E80_BRIDGE_H
#define E80_BRIDGE_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Switch the E80 from the bench console to the binary FIPS bridge protocol. */
void bridge_start(void);

/** True once bridge_start() has run. */
bool bridge_active(void);

/** Superloop task: serial protocol + radio events. Never call radio_task(). */
void bridge_task(void);

#ifdef __cplusplus
}
#endif

#endif
