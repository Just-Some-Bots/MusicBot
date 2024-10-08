---
title: Permissions
category: Using the bot
order: 2
---

This page gives information on how to setup **permissions**. When you install the bot, you will get a file inside the `config` folder named `example_permissions.ini`. This option contains an **example set** of permissions. Edit it, and then **save it as a new file** called `permissions.ini`.

> For Windows users, please note that file extensions are **hidden by default**, so you may just need to save the file as `permissions` if you are having difficulties as the `.ini` may be hidden.

> Do not edit any configuration file using Notepad or other basic text editors, otherwise it will break. Use something like [Notepad++](https://notepad-plus-plus.org/download/).

The permissions file contains **multiple sections**. The `[Default]` section should **not be renamed**. It contains the default permissions for users of the bot that are not the owner. **Each section is a group**. A user's roles do not allow them to have full permissions to use the bot, **this file does**.

#### Control what commands a group can use
**Add the command** in the `CommandWhitelist` section of the group. Each command should be separated by **spaces**. For example, to allow a group to use `!play` and `!skip` only:

    CommandWhitelist = play skip

#### Add a user to a group
**Add a user's ID** in the `UserList` section of the group. Each user ID should be separated by **spaces**. For example:

    UserList = 154748625350688768 104766296687656960

#### Add a role to a group

**Add a role's ID** in the `GrantToRoles` section of the group. Each role ID should be separated by **spaces**. For example:

    GrantToRoles = 173129876679688192 183343083063214081

However, **don't add an ID to the Default group!** This group is assigned to everyone that doesn't have any other groups assigned and therefore needs no ID.
