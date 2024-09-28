
# Permission System
There are two roles in the system: Admin and User (you can treat then as buckets).  

## `PUT` and `DELETE` permissions
Non-login user don't have `PUT/DELETE` permissions.  
Every user can have `PUT/DELETE` permissions of files under its own `/<user>/` path.  
The admin can have `PUT/DELETE` permissions of files of all users.

## `GET` permissions
The `GET` is used to access the file (if path is not ending with `/`), or to list the files under a path (if path is ending with `/`). 

### Path-listing
- Non-login users cannot list any files.
- All users can list the files under their own path 
- Admins can list the files under other users' path. 

### File-access
For accessing file content, the user must have `GET` permission of the file, which is determined by the `permission` field of both the owner and the file. 
(Note: The owner of the file is the user who created the file, may not necessarily be the user under whose path the file is stored.)   

There are four types of permissions: `unset`, `public`, `protected`, `private`.
Non-admin users can access files based on:   

- If the file is `public`, then all users can access it.
- If the file is `protected`, then only the logged-in user can access it.  
- If the file is `private`, then only the owner can access it.
- If the file is `unset`, then the file's permission is inherited from the owner's permission.
- If both the owner and the file have `unset` permission, then the file is `public`.