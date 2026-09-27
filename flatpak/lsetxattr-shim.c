/* LD_PRELOAD shim for the flatpak/ostree xattr regression.
 *
 * ONLY needed on hosts where `flatpak build-init --base=...` aborts with:
 *
 *   error: lsetxattr(security.selinux): Operation not supported
 *
 * That is flatpak issue #6818: a regression introduced after 1.17.6 and fixed
 * in flatpak 1.18.3 / the matching ostree release. Fedora 44 shipped 1.18.2 and
 * ostree 2026.4, which still contain it. Prefer upgrading flatpak and ostree;
 * use this shim only when no fixed package is available yet.
 *
 * Two failures have to be worked around, both while checking out a BaseApp:
 *
 *   1. libglnx sets xattrs through the path /proc/self/fd/N. /proc/self/fd/N is
 *      a symlink, so lsetxattr() tries to label the magic link itself and the
 *      kernel answers EOPNOTSUPP. Following the link with setxattr() works.
 *
 *   2. BaseApp commits carry a security.selinux label, which libostree applies
 *      as a plain xattr. An unprivileged user is not allowed to set it, so the
 *      call fails with EACCES instead. Skipping that one label is harmless for a
 *      local build: the files are relabelled from the host policy when the
 *      bundle is installed.
 *
 * Build and use (the build script does this automatically when it detects the
 * regression):
 *
 *   cc -shared -fPIC -O2 -o lsetxattr-shim.so lsetxattr-shim.c -ldl
 *   LD_PRELOAD=$PWD/lsetxattr-shim.so flatpak-builder ...
 */

#define _GNU_SOURCE

#include <dlfcn.h>
#include <string.h>
#include <sys/xattr.h>

typedef int (*xattr_fn)(const char *, const char *, const void *, size_t, int);

static xattr_fn real_setxattr = NULL;
static xattr_fn real_lsetxattr = NULL;

/* The one label an unprivileged process may not set; ignore that failure only. */
static int keep_selinux_label(const char *name, int result)
{
    if (result == -1 && name != NULL && strcmp(name, "security.selinux") == 0)
        return 0;
    return result;
}

int setxattr(const char *path, const char *name, const void *value, size_t size, int flags)
{
    if (real_setxattr == NULL)
        real_setxattr = (xattr_fn)dlsym(RTLD_NEXT, "setxattr");
    return keep_selinux_label(name, real_setxattr(path, name, value, size, flags));
}

int lsetxattr(const char *path, const char *name, const void *value, size_t size, int flags)
{
    if (real_setxattr == NULL)
        real_setxattr = (xattr_fn)dlsym(RTLD_NEXT, "setxattr");
    if (real_lsetxattr == NULL)
        real_lsetxattr = (xattr_fn)dlsym(RTLD_NEXT, "lsetxattr");

    /* /proc/self/fd/N refers to an already-open file; the magic link in /proc is
     * a symlink, so it must be followed rather than labelled. */
    if (path != NULL && strncmp(path, "/proc/self/fd/", 14) == 0)
        return keep_selinux_label(name, real_setxattr(path, name, value, size, flags));

    return keep_selinux_label(name, real_lsetxattr(path, name, value, size, flags));
}
