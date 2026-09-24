/*
 * Userspace ntsync backend (ntsync-android)
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA
 */

/* Declarations for libntsync_android (https://github.com/GameNative/ntsync-android),
 * a userspace replacement for the Linux /dev/ntsync driver for devices that
 * don't have it. Objects live in a shared memory region and are named by u32
 * handles instead of file descriptors; the argument structures are the kernel
 * uapi ones from ntsync.h, which the library mirrors exactly.
 *
 * wineserver creates and destroys every object; clients only operate on them.
 * In userspace mode the handle takes the place of the object fd everywhere, so
 * the ioctl-based code paths only need ntsync_userspace_ioctl() below. */

#ifndef __WINE_NTSYNC_ANDROID_H
#define __WINE_NTSYNC_ANDROID_H

#include <errno.h>
#include <stdint.h>
#include <sys/ioctl.h>

#include "ntsync.h"

extern int32_t ntsync_init( const char *path );
extern int32_t ntsync_sweep_dead( void );
extern int32_t ntsync_create_sem( uint32_t *out_handle, const struct ntsync_sem_args *args );
extern int32_t ntsync_create_mutex( uint32_t *out_handle, const struct ntsync_mutex_args *args );
extern int32_t ntsync_create_event( uint32_t *out_handle, const struct ntsync_event_args *args );
extern int32_t ntsync_close( uint32_t handle );
extern int32_t ntsync_sem_release( uint32_t handle, uint32_t *count );
extern int32_t ntsync_sem_read( uint32_t handle, struct ntsync_sem_args *args );
extern int32_t ntsync_mutex_unlock( uint32_t handle, struct ntsync_mutex_args *args );
extern int32_t ntsync_mutex_kill( uint32_t handle, uint32_t owner );
extern int32_t ntsync_mutex_read( uint32_t handle, struct ntsync_mutex_args *args );
extern int32_t ntsync_event_set( uint32_t handle, uint32_t *prev );
extern int32_t ntsync_event_reset( uint32_t handle, uint32_t *prev );
extern int32_t ntsync_event_pulse( uint32_t handle, uint32_t *prev );
extern int32_t ntsync_event_read( uint32_t handle, struct ntsync_event_args *args );
extern int32_t ntsync_wait_any( struct ntsync_wait_args *args );
extern int32_t ntsync_wait_all( struct ntsync_wait_args *args );

/* Same contract as ioctl() on an ntsync fd: the create requests return the new
 * object (a handle here, an fd from the kernel), everything else returns 0;
 * failures return -1 and set errno. "obj" is ignored for the wait requests,
 * which the kernel issues on the device fd. */
static inline int ntsync_userspace_ioctl( int obj, unsigned long request, void *arg )
{
    uint32_t handle = 0;
    int32_t ret;

    switch (request)
    {
    case NTSYNC_IOC_CREATE_SEM:   ret = ntsync_create_sem( &handle, arg ); break;
    case NTSYNC_IOC_CREATE_MUTEX: ret = ntsync_create_mutex( &handle, arg ); break;
    case NTSYNC_IOC_CREATE_EVENT: ret = ntsync_create_event( &handle, arg ); break;
    case NTSYNC_IOC_SEM_RELEASE:  ret = ntsync_sem_release( obj, arg ); break;
    case NTSYNC_IOC_SEM_READ:     ret = ntsync_sem_read( obj, arg ); break;
    case NTSYNC_IOC_MUTEX_UNLOCK: ret = ntsync_mutex_unlock( obj, arg ); break;
    case NTSYNC_IOC_MUTEX_KILL:   ret = ntsync_mutex_kill( obj, *(uint32_t *)arg ); break;
    case NTSYNC_IOC_MUTEX_READ:   ret = ntsync_mutex_read( obj, arg ); break;
    case NTSYNC_IOC_EVENT_SET:    ret = ntsync_event_set( obj, arg ); break;
    case NTSYNC_IOC_EVENT_RESET:  ret = ntsync_event_reset( obj, arg ); break;
    case NTSYNC_IOC_EVENT_PULSE:  ret = ntsync_event_pulse( obj, arg ); break;
    case NTSYNC_IOC_EVENT_READ:   ret = ntsync_event_read( obj, arg ); break;
    case NTSYNC_IOC_WAIT_ANY:     ret = ntsync_wait_any( arg ); break;
    case NTSYNC_IOC_WAIT_ALL:     ret = ntsync_wait_all( arg ); break;
    default:                      ret = -ENOTTY; break;
    }

    if (ret < 0)
    {
        errno = -ret;
        return -1;
    }
    return handle;
}

#endif /* __WINE_NTSYNC_ANDROID_H */
