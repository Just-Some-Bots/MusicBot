---
title: Errors
position: 3
---

| Code | Name        | Description                      |
|------|-------------|----------------------------------|
| 200  | OK          | Success                          |
| 201  | Created     | Creation Successful              |
| 400  | Bad Request | We could not process that action |
| 403  | Forbidden   | We couldn't authenticate you     |

All errors will return JSON in the following format:

~~~ json
{
  "error": true,
  "message": "error message here"
}
~~~
