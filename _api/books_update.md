---
title: /books/:id
position: 1.4
type: put
description: Update Book
right_code: |
  ~~~ json
  {
    "id": 3,
    "title": "The Book Stealer",
    "score": 5,
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

title
: The title for the book

score
: The book's score between 0 and 5

Update an existing book in your collection.

~~~ javascript
$.ajax({
  "url": "http://api.myapp.com/books/3",
  "type": "PUT",
  "data": {
    "token": "YOUR_APP_KEY",
    "score": 5.0,
    "title": "The Book Stealer"
  },
  "success": function(data) {
    alert(data);
  }
});
~~~
{: title="jQuery" }
