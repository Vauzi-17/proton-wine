/*
 * In-process synchronization primitives
 *
 * Copyright (C) 2021-2022 Elizabeth Figura for CodeWeavers
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

#include "config.h"

#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>

#include "ntstatus.h"
#define WIN32_NO_STATUS
#include "winternl.h"

#include "file.h"
#include "handle.h"
#include "request.h"
#include "thread.h"
#ifdef HAVE_LINUX_TYPES_H
# include "ntsync.h"
#endif
#ifdef HAVE_NTSYNC_ANDROID
# include "ntsync_android.h"
#endif

#ifdef HAVE_LINUX_NTSYNC_H

#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>

/* which implementation backs the in-process synchronization objects */
enum ntsync_backend
{
    NTSYNC_BACKEND_UNKNOWN = -1,
    NTSYNC_BACKEND_NONE,        /* server-side synchronization (or esync/fsync) */
    NTSYNC_BACKEND_KERNEL,      /* /dev/ntsync */
    NTSYNC_BACKEND_USERSPACE,   /* libntsync_android shared memory region */
};

static enum ntsync_backend ntsync_backend = NTSYNC_BACKEND_UNKNOWN;

struct linux_device
{
    struct object obj;      /* object header */
    struct fd *fd;          /* fd for unix fd, NULL for the userspace backend */
};

static struct linux_device *linux_device_object;

static void linux_device_dump( struct object *obj, int verbose );
static struct fd *linux_device_get_fd( struct object *obj );
static void linux_device_destroy( struct object *obj );
static enum server_fd_type inproc_sync_get_fd_type( struct fd *fd );

static const struct object_ops linux_device_ops =
{
    sizeof(struct linux_device),        /* size */
    &no_type,                           /* type */
    linux_device_dump,                  /* dump */
    no_add_queue,                       /* add_queue */
    NULL,                               /* remove_queue */
    NULL,                               /* signaled */
    NULL,                               /* get_esync_fd */
    NULL,                               /* get_fsync_idx */
    NULL,                               /* satisfied */
    no_signal,                          /* signal */
    linux_device_get_fd,                /* get_fd */
    default_map_access,                 /* map_access */
    default_get_sd,                     /* get_sd */
    default_set_sd,                     /* set_sd */
    no_get_full_name,                   /* get_full_name */
    no_lookup_name,                     /* lookup_name */
    no_link_name,                       /* link_name */
    NULL,                               /* unlink_name */
    no_open_file,                       /* open_file */
    no_kernel_obj_list,                 /* get_kernel_obj_list */
    no_get_inproc_sync,                 /* get_inproc_sync */
    no_close_handle,                    /* close_handle */
    linux_device_destroy                /* destroy */
};

static const struct fd_ops inproc_sync_fd_ops =
{
    default_fd_get_poll_events,     /* get_poll_events */
    default_poll_event,             /* poll_event */
    inproc_sync_get_fd_type,        /* get_fd_type */
    no_fd_read,                     /* read */
    no_fd_write,                    /* write */
    no_fd_flush,                    /* flush */
    no_fd_get_file_info,            /* get_file_info */
    no_fd_get_volume_info,          /* get_volume_info */
    no_fd_ioctl,                    /* ioctl */
    default_fd_cancel_async,        /* cancel_async */
    no_fd_queue_async,              /* queue_async */
    default_fd_reselect_async       /* reselect_async */
};

static void linux_device_dump( struct object *obj, int verbose )
{
    struct linux_device *device = (struct linux_device *)obj;
    assert( obj->ops == &linux_device_ops );
    fprintf( stderr, "In-process synchronization device fd=%p\n", device->fd );
}

static struct fd *linux_device_get_fd( struct object *obj )
{
    struct linux_device *device = (struct linux_device *)obj;
    if (!device->fd)
    {
        set_error( STATUS_OBJECT_TYPE_MISMATCH );
        return NULL;
    }
    return (struct fd *)grab_object( device->fd );
}

static void linux_device_destroy( struct object *obj )
{
    struct linux_device *device = (struct linux_device *)obj;
    assert( obj->ops == &linux_device_ops );
    if (device->fd) release_object( device->fd );
    linux_device_object = NULL;
}

static enum server_fd_type inproc_sync_get_fd_type( struct fd *fd )
{
    return FD_TYPE_FILE;
}

static int get_ntsync_fd(void)
{
    int fd = open( "/dev/ntsync", O_CLOEXEC | O_RDONLY );
    if (fd == -1)
    {
        static int once;
        file_set_error();
        if (!once++) fprintf( stderr, "Cannot open synchronization device: %s\n", strerror( errno ) );
        return 0;
    }
    return fd;
}

static struct linux_device *get_linux_device(void)
{
    struct linux_device *device;
    static int initialized;
    int unix_fd;

    if (!do_ntsync())
    {
        set_error( STATUS_NOT_IMPLEMENTED );
        return NULL;
    }

    if (initialized)
    {
        if (linux_device_object)
            grab_object( linux_device_object );
	else
	  set_error( STATUS_NOT_IMPLEMENTED );
        return linux_device_object;
    }

    if (ntsync_backend == NTSYNC_BACKEND_USERSPACE)
    {
        /* no device fd: objects are handles into the shared region */
        if (!(device = alloc_object( &linux_device_ops )))
        {
            set_error( STATUS_NO_MEMORY );
            initialized = 1;
            return NULL;
        }
        device->fd = NULL;
        fprintf( stderr, "wine: using fast synchronization (userspace ntsync).\n" );
        /* clients get no handle to this device, so the cached pointer must
         * hold its own reference or the first release destroys it */
        linux_device_object = (struct linux_device *)grab_object( device );
        initialized = 1;
        return device;
    }

    if (!(unix_fd = get_ntsync_fd())) return NULL;

    if (!(device = alloc_object( &linux_device_ops )))
    {
        close( unix_fd );
        set_error( STATUS_NO_MEMORY );
	initialized = 1;
        return NULL;
    }

    if (!(device->fd = create_anonymous_fd( &inproc_sync_fd_ops, unix_fd, &device->obj, 0 )))
    {
        release_object( device );
	initialized = 1;
        return NULL;
    }

    fprintf( stderr, "wine: using fast synchronization.\n" );
    /* Keep a reference for the cached pointer. Client handles used to be the
     * only thing keeping the device alive, and once "initialized" is set a
     * destroyed device is never recreated: ntsync silently stopped working
     * as soon as every client had exited (e.g. with a persistent wineserver),
     * or if an object was created before any client asked for the device. */
    linux_device_object = (struct linux_device *)grab_object( device );
    initialized = 1;
    return device;
}

static int env_set( const char *name )
{
    const char *value = getenv( name );
    return value && atoi( value );
}

/* The device node can exist and still be unusable (SELinux policy, seccomp),
 * so create a real object on it before trusting it. */
static int kernel_ntsync_usable(void)
{
    struct ntsync_event_args args = {0};
    int device, event;

    if ((device = open( "/dev/ntsync", O_CLOEXEC | O_RDONLY )) == -1) return 0;
    event = ioctl( device, NTSYNC_IOC_CREATE_EVENT, &args );
    if (event >= 0) close( event );
    close( device );
    return event >= 0;
}

/* Called from main() before esync/fsync are initialized, so this must not
 * create any server objects; get_linux_device() does that later. */
static enum ntsync_backend get_ntsync_backend(void)
{
    if (ntsync_backend != NTSYNC_BACKEND_UNKNOWN) return ntsync_backend;

    ntsync_backend = NTSYNC_BACKEND_NONE;

    if (env_set( "WINE_DISABLE_FAST_SYNC" ) || env_set( "PROTON_NO_NTSYNC" ) ||
        (getenv( "WINENTSYNC" ) && !atoi( getenv( "WINENTSYNC" ) )))
    {
        fprintf( stderr, "ntsync is explicitly disabled.\n" );
        return ntsync_backend;
    }

    if (env_set( "PROTON_NO_KERNEL_NTSYNC" ))
        fprintf( stderr, "ntsync: PROTON_NO_KERNEL_NTSYNC set, not using /dev/ntsync.\n" );
    else if (kernel_ntsync_usable())
        return ntsync_backend = NTSYNC_BACKEND_KERNEL;

#ifdef HAVE_NTSYNC_ANDROID
    if (!ntsync_init( NULL ))
    {
        fprintf( stderr, "ntsync: no usable /dev/ntsync, using userspace ntsync.\n" );
        return ntsync_backend = NTSYNC_BACKEND_USERSPACE;
    }
    fprintf( stderr, "ntsync: userspace ntsync failed to initialize (is TMPDIR or NTSYNC_SHM set?).\n" );
#endif
    return ntsync_backend;
}

int do_ntsync(void)
{
    return get_ntsync_backend() != NTSYNC_BACKEND_NONE;
}

static int ntsync_userspace(void)
{
    return get_ntsync_backend() == NTSYNC_BACKEND_USERSPACE;
}

struct inproc_sync
{
    struct object obj;
    enum inproc_sync_type type;
    struct fd *fd;                  /* kernel backend */
    unsigned int userspace_handle;  /* userspace backend */
};

/* ioctl() on the object, dispatched to whichever backend is in use */
static int inproc_sync_ioctl( struct inproc_sync *inproc_sync, unsigned long request, void *arg )
{
#ifdef HAVE_NTSYNC_ANDROID
    if (!inproc_sync->fd) return ntsync_userspace_ioctl( inproc_sync->userspace_handle, request, arg );
#endif
    return ioctl( get_unix_fd( inproc_sync->fd ), request, arg );
}

/* create an object on the device; returns an fd (kernel) or a handle (userspace) */
static int linux_device_ioctl( struct linux_device *device, unsigned long request, void *arg )
{
#ifdef HAVE_NTSYNC_ANDROID
    if (!device->fd) return ntsync_userspace_ioctl( -1, request, arg );
#endif
    return ioctl( get_unix_fd( device->fd ), request, arg );
}

static void linux_obj_dump( struct object *obj, int verbose );
static void linux_obj_destroy( struct object *obj );
static struct fd *linux_obj_get_fd( struct object *obj );

static const struct object_ops linux_obj_ops =
{
    sizeof(struct inproc_sync), /* size */
    &no_type,                   /* type */
    linux_obj_dump,             /* dump */
    no_add_queue,               /* add_queue */
    NULL,                       /* remove_queue */
    NULL,                       /* signaled */
    NULL,                       /* get_esync_fd */
    NULL,                       /* get_fsync_idx */
    NULL,                       /* satisfied */
    no_signal,                  /* signal */
    linux_obj_get_fd,           /* get_fd */
    default_map_access,         /* map_access */
    default_get_sd,             /* get_sd */
    default_set_sd,             /* set_sd */
    no_get_full_name,           /* get_full_name */
    no_lookup_name,             /* lookup_name */
    no_link_name,               /* link_name */
    NULL,                       /* unlink_name */
    no_open_file,               /* open_file */
    no_kernel_obj_list,         /* get_kernel_obj_list */
    no_get_inproc_sync,         /* get_inproc_sync */
    no_close_handle,            /* close_handle */
    linux_obj_destroy           /* destroy */
};

static void linux_obj_dump( struct object *obj, int verbose )
{
    struct inproc_sync *inproc_sync = (struct inproc_sync *)obj;
    assert( obj->ops == &linux_obj_ops );
    fprintf( stderr, "In-process synchronization object type=%u fd=%p handle=%u\n",
             inproc_sync->type, inproc_sync->fd, inproc_sync->userspace_handle );
}

static void linux_obj_destroy( struct object *obj )
{
    struct inproc_sync *inproc_sync = (struct inproc_sync *)obj;
    assert( obj->ops == &linux_obj_ops );
    if (inproc_sync->fd) release_object( inproc_sync->fd );
#ifdef HAVE_NTSYNC_ANDROID
    else if (inproc_sync->userspace_handle) ntsync_close( inproc_sync->userspace_handle );
#endif
}

static struct fd *linux_obj_get_fd( struct object *obj )
{
    struct inproc_sync *inproc_sync = (struct inproc_sync *)obj;
    assert( obj->ops == &linux_obj_ops );
    if (!inproc_sync->fd)
    {
        set_error( STATUS_OBJECT_TYPE_MISMATCH );
        return NULL;
    }
    return (struct fd *)grab_object( inproc_sync->fd );
}

/* "obj" is what linux_device_ioctl() returned for the create request:
 * an fd for the kernel backend, a handle for the userspace one */
static struct inproc_sync *create_inproc_sync( enum inproc_sync_type type, int obj )
{
    int userspace = ntsync_userspace();
    struct inproc_sync *inproc_sync;

    if (!(inproc_sync = alloc_object( &linux_obj_ops )))
    {
#ifdef HAVE_NTSYNC_ANDROID
        if (userspace) ntsync_close( obj );
        else
#endif
        close( obj );
        return NULL;
    }

    inproc_sync->type = type;
    inproc_sync->fd = NULL;
    inproc_sync->userspace_handle = 0;

    if (userspace)
    {
        inproc_sync->userspace_handle = obj;
        return inproc_sync;
    }

    if (!(inproc_sync->fd = create_anonymous_fd( &inproc_sync_fd_ops, obj, &inproc_sync->obj, 0 )))
    {
        release_object( inproc_sync );
        return NULL;
    }

    return inproc_sync;
}

struct inproc_sync *create_inproc_event( enum inproc_sync_type type, int signaled )
{
    struct ntsync_event_args args;
    struct linux_device *device;
    int event;

    if (!(device = get_linux_device())) return NULL;

    args.signaled = signaled;
    switch (type)
    {
        case INPROC_SYNC_AUTO_EVENT:
        case INPROC_SYNC_AUTO_SERVER:
            args.manual = 0;
            break;

        case INPROC_SYNC_MANUAL_EVENT:
        case INPROC_SYNC_MANUAL_SERVER:
        case INPROC_SYNC_QUEUE:
            args.manual = 1;
            break;

        case INPROC_SYNC_MUTEX:
        case INPROC_SYNC_SEMAPHORE:
            assert(0);
            break;
    }
    if ((event = linux_device_ioctl( device, NTSYNC_IOC_CREATE_EVENT, &args )) < 0)
    {
        file_set_error();
        release_object( device );
        return NULL;
    }
    release_object( device );

    return create_inproc_sync( type, event );
}

struct inproc_sync *create_inproc_semaphore( unsigned int count, unsigned int max )
{
    struct ntsync_sem_args args;
    struct linux_device *device;
    int semaphore;

    if (!(device = get_linux_device())) return NULL;

    args.count = count;
    args.max = max;
    if ((semaphore = linux_device_ioctl( device, NTSYNC_IOC_CREATE_SEM, &args )) < 0)
    {
        file_set_error();
        release_object( device );
        return NULL;
    }

    release_object( device );

    return create_inproc_sync( INPROC_SYNC_SEMAPHORE, semaphore );
}

struct inproc_sync *create_inproc_mutex( thread_id_t owner, unsigned int count )
{
    struct ntsync_mutex_args args;
    struct linux_device *device;
    int mutex;

    if (!(device = get_linux_device())) return NULL;

    args.owner = owner;
    args.count = count;
    if ((mutex = linux_device_ioctl( device, NTSYNC_IOC_CREATE_MUTEX, &args )) < 0)
    {
        file_set_error();
        release_object( device );
        return NULL;
    }

    release_object( device );

    return create_inproc_sync( INPROC_SYNC_MUTEX, mutex );
}

void set_inproc_event( struct inproc_sync *inproc_sync )
{
    __u32 count;

    if (!inproc_sync) return;

    if (debug_level) fprintf( stderr, "set_inproc_event %p\n", inproc_sync->fd );

    inproc_sync_ioctl( inproc_sync, NTSYNC_IOC_EVENT_SET, &count );
}

void reset_inproc_event( struct inproc_sync *inproc_sync )
{
    __u32 count;

    if (!inproc_sync) return;

    if (debug_level) fprintf( stderr, "reset_inproc_event %p\n", inproc_sync->fd );

    inproc_sync_ioctl( inproc_sync, NTSYNC_IOC_EVENT_RESET, &count );
}

void abandon_inproc_mutex( thread_id_t tid, struct inproc_sync *inproc_sync )
{
    inproc_sync_ioctl( inproc_sync, NTSYNC_IOC_MUTEX_KILL, &tid );
}

#else

struct inproc_sync *create_inproc_event( enum inproc_sync_type type, int signaled )
{
    set_error( STATUS_NOT_IMPLEMENTED );
    return NULL;
}

struct inproc_sync *create_inproc_semaphore( unsigned int count, unsigned int max )
{
    set_error( STATUS_NOT_IMPLEMENTED );
    return NULL;
}

struct inproc_sync *create_inproc_mutex( thread_id_t owner, unsigned int count )
{
    set_error( STATUS_NOT_IMPLEMENTED );
    return NULL;
}

void set_inproc_event( struct inproc_sync *inproc_sync )
{
}

void reset_inproc_event( struct inproc_sync *obj )
{
}

void abandon_inproc_mutex( thread_id_t tid, struct inproc_sync *inproc_sync )
{
}

int do_ntsync(void)
{
    set_error( STATUS_NOT_IMPLEMENTED );
    return 0;
}

#endif

DECL_HANDLER(get_linux_sync_device)
{
#ifdef HAVE_LINUX_NTSYNC_H
    struct linux_device *device;

    if ((device = get_linux_device()))
    {
        /* the userspace backend has no device fd to pass; clients attach to
         * the shared region themselves */
        if (device->fd) reply->handle = alloc_handle_no_access_check( current->process, device, 0, 0 );
        reply->userspace = !device->fd;
        release_object( device );
    }
#else
    set_error( STATUS_NOT_IMPLEMENTED );
#endif
}

DECL_HANDLER(get_linux_sync_obj)
{
#ifdef HAVE_LINUX_NTSYNC_H
    struct object *obj;

    if ((obj = get_handle_obj( current->process, req->handle, 0, NULL )))
    {
        struct inproc_sync *inproc_sync;

        if ((inproc_sync = obj->ops->get_inproc_sync( obj )))
        {
            reply->handle = alloc_handle_no_access_check( current->process, inproc_sync, 0, 0 );
            reply->userspace_handle = inproc_sync->userspace_handle;
            reply->type = inproc_sync->type;
            reply->access = get_handle_access( current->process, req->handle );
            release_object( inproc_sync );
        }
        release_object( obj );
    }
#else
    set_error( STATUS_NOT_IMPLEMENTED );
#endif
}
