
# Permission System
There are two user roles in the system: Admin and Normal User ("users" are like "buckets" to some extent).

## Ownership
A file is owned by the user who created it, may not necessarily be the user under whose path the file is stored (admin can create files under any user's path).

## File access with `GET` permission
The `GET` is used to access the file (if path is not ending with `/`), or to list the files under a path (if path is ending with `/`).  

### File access
For accessing file content, the user must have `GET` permission of the file, which is determined by the `permission` field of both the owner and the file.   

There are four types of permissions: `unset`, `public`, `protected`, `private`.
Non-admin users can access files based on:   

- If the file is `public`, then all users can access it.
- If the file is `protected`, then only the logged-in user can access it.  
- If the file is `private`, then only the owner can access it.
- If the file is `unset`, then the file's permission is inherited from the owner's permission.
- If both the owner and the file have `unset` permission, then the file is `public`.

### Meta-data access
- Non-login users can't access any file-meta.
- All users can access the file-meta of files under their own path.
- For files under other users' path, the file-meta is determined in a way same as file access.
- Admins can access the path-meta of all users.
- All users can access the path-meta of their own path.

### Path-listing
- Non-login users cannot list any files.
- All users can list the files under their own path 
- Admins can list the files under other users' path. 

## File creation with `PUT` permission
The `PUT` is used to create a file. 
- Non-login user don't have `PUT` permission.  
- Every user can have `PUT` permission of files under its own `/<user>/` path.  
- The admin can have `PUT` permission of files of all users.

## `DELETE` and moving permissions
- Non-login user don't have `DELETE`/move permission.
- Every user can have `DELETE`/move permission that they own.
- The admin can have `DELETE` permission of files of all users
(The admin can't move files of other users, because move does not change the owner of the file. 
If move is allowed, then its equivalent to create file on behalf of other users.)