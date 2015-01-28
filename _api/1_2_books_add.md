---
title: /books
type: post
description: Create Book
parameters:
  title: Create Book Format
  data:
    - title:
      - string
      - The title for the book
    - score:
      - float
      - The book's score between 0 and 5
right_code:
  response: |
    {
      "id": 3,
      "title": "The Book Thief",
      "score": 4.3,
      "date_added": "5/1/2015"
    }
---

Adds a book to your collection.

<div class="code-viewer">
  <pre data-language="jQuery">
  $.post('http://api.myapp.com/books/', {
    token: 'YOUR_APP_KEY',
    title: "The Book Thief",
    score: 4.3
  }, function(data) {
    alert(data);
  });</pre>
</div>
