
# Permission System
There are two user roles in the system: Admin and Normal User ("users" are like "buckets" to some extent).  
A user have all permissions of the files and subpaths under its path (starting with `/<user>/`).  
Admins have all permissions of all files and paths.

> **path** ends with `/` and **file** does not end with `/`.

## Peers
The user can have multiple peer users. The peer user can have read or write access to the user's path, depending on the access level set when adding the peer user.  
The peer user can list the files under the user's path.  
If the peer user only has read access (peer-r), then the peer user can only `GET` files under the user's path.  
If the peer user has write access (peer-w), then the peer user can `GET`/`PUT`/`POST`/`DELETE` files under the user's path.  

## Ownership
A file is owned by the user who created it, may not necessarily be the user under whose path the file is stored (admin/write-peer can create files under any user's path).

# Non-peer and public access

**NOTE:** below discussion is based on the assumption that the user is not a peer of the path owner, or is guest user (public access).

## File access with `GET` permission

### File access
For accessing file content, the user must have `GET` permission of the file, which is determined by the `permission` field of both the path-owner and the file.   

There are four types of permissions: `unset`, `public`, `protected`, `private`.
Non-admin users can access files based on:   

- If the file is `public`, then all users can access it.
- If the file is `protected`, then only the logged-in user can access it.  
- If the file is `private`, then only the owner/path-owner can access it.
- If the file is `unset`, then the file's permission is inherited from the path-owner's permission.
- If both the path-owner and the file have `unset` permission, then the file is `public`.

## File creation with `PUT`/`POST` permission
`PUT`/`POST` permission is not allowed for non-peer users.

## File `DELETE` and moving permissions
- Non-login user don't have `DELETE`/move permission.
- Every user can have `DELETE` permission that they own.
- User can move files if they have write access to the destination path.

## Path-listing
Path-listing is not allowed for these users.

# Summary

| Permission | Admin | User | Peer-r | Peer-w | Owner (not the user) | Non-peer user / Guest  |
|------------|-------|------|--------|--------|----------------------|------------------------|
| GET        | Yes   | Yes  | Yes    | Yes    | Yes                  | Depends on file        |
| PUT/POST   | Yes   | Yes  | No     | Yes    | Yes                  | No                     |
| DELETE file| Yes   | Yes  | No     | Yes    | Yes                  | No                     | 
| DELETE path| Yes   | Yes  | No     | Yes    | N/A                  | No                     | 
| move       | Yes   | Yes  | No     | Yes    | Dep. on destination  | No                     |
| list       | Yes   | Yes  | Yes    | Yes    | No if not peer       | No                     |

> Capitilized methods are HTTP methods, N/A means not applicable.
