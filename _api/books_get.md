---
title: /books/:id
position: 1.3
type: get
description: Get Book
right_code: |
  ~~~ json
  {
    "id": 3,
    "title": "The Book Thief",
    "score": 4.3,
    "dateAdded": "5/1/2015"
  }
  ~~~
  {: title="Response" }

  ~~~ json
  {
    "error": true,
    "message": "Book doesn't exist"
  }
  ~~~
  {: title="Error" }
---

Returns a specific book from your collection

~~~ javascript
$.get("http://api.myapp.com/books/3", {
  token: "YOUR_APP_KEY",
}, function(data) {
  alert(data);
});
~~~
{: title="jQuery" }
