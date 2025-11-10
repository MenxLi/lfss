
# Permission System

Current permission system is designed around **access levels** and single file **permission** settings.

There are different access levels for different users, which determine what operations they can perform on files and directories. Higher access levels grant more permissions.
- <span class="perm">admin/all</span>: all permissions including `GET`/`PUT`/`POST`/`DELETE` and listing directories.
- <span class="perm">write</span>: same as admin except for [directory configuration](./lfssdir.md) file.
- <span class="perm">read</span>: only `GET` permission and listing directories.
- <span class="perm">none</span>: no permissions.

## User Roles
There are two user roles in the system: Admin and Normal User ("users" are like "buckets" to some extent).  
A user have <span class="perm">all</span> permissions of the files and directories under its path (starting with `/<user>/`). 
Admins have <span class="perm">admin</span> permissions of all files and directories.

> **directory** path ends with `/` and **file** does not end with `/`.

### Ownership
There are two types of ownership for files (terms used in permission checks):
- **file-owner**: the user who created the file.
- **path-owner**: the user under whose path the file is stored (*i.e.* `/<username>/...`).  

The owner always has <span class="perm">all</span> permissions of the file.

::: info 
A file is owned by the user who created it. `move` will change the owner of the file. `copy` will create a new file owned by the user who performed the copy.
:::

### Peer Users
The user can have multiple peer users. 
The peer user can have <span class="perm">read</span> or <span class="perm">write</span> access to the user's path, depending on the access level set when adding the peer user.

:::info
Peer relations can be overridden by single directory permission settings, 
please refer to the [Single Directory Configuration](./lfssdir.md) document for more details.
:::

## Move/Copy Permission
When moving or copying files, the user must have <span class="perm">write</span> permission of the corresponding paths. 
- `move` operation also requires *write* permission of both the source and destination paths.
- `copy` operation does not require *write* permission of the source path.

## Non-peer and public access

:::info NOTE
This section discusses scenarios where the user is neither a peer of the path owner nor a logged-in user (i.e., guest or public access). It focuses on permissions for files and directories under other users' paths. 
:::

Users who are not logged in and are not peers of the path owner have limited access to files and directories under the users' paths. 
Specifically, they only have <span class="perm">none</span> permissions and cannot list directories. 
For directy access via file link, their permissions depend on the file's **permission** settings, as described below.

### File access with `GET` permission

For accessing file content via direct link, the user must have `GET` permission of the file, 
which is determined by the `permission` field of both the path-owner and the file.   

There are four types of permissions: `unset`, `public`, `protected`, `private`.
Non-admin users can access files based on:   

- If the file is `public`, then all users can access it.
- If the file is `protected`, then only the logged-in user can access it.  
- If the file is `private`, then only the owner/path-owner can access it.
- If the file is `unset`, then the file's permission is inherited from the path-owner's permission.
- If both the path-owner and the file have `unset` permission, then the file is `public`.

# Summary

For quick reference, here is a summary table of the permission system: 
:::info Note
The table assumes the user is accessing files/directories under another user's path 
(The path-owner always has all permissions under its own path). 
The permission is considered in the order of left to right, and the first matching condition applies.
:::


| Permission | Admin | Peer-w | Peer-r | File Owner | Non-peer user / Guest  |
|------------|-------|--------|--------|------------|------------------------|
| GET        | Yes   | Yes    | Yes    | Yes        | Dep.                   |
| PUT/POST   | Yes   | Yes    | No     | Yes        | No                     |
| DELETE file| Yes   | Yes    | No     | Yes        | No                     | 
| DELETE dir | Yes   | Yes    | No     | No         | No                     | 
| move       | Yes   | Yes    | No     | Dep.       | No                     |
| copy       | Yes   | Yes    | Dep.   | Dep.       | No                     |
| list       | Yes   | Yes    | Yes    | No         | No                     |


> Capitilized methods are HTTP methods.   
> "Dep." means "Depends on file" or "Depends on source and destination".

<style scoped>
    span.perm{
        font-family: monospace;
        background-color: #f0f0f033;
        color: #394;
        padding: 2px 4px;
        border-radius: 4px;
    }
</style>