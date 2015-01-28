---
title: /books/:id
type: put
description: Update Book
parameters:
  title: Update Book Format
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
      "title": "The Book Stealer",
      "score": 5,
      "date_added": "5/1/2015"
    }
---

Update an existing book in your collection.

<div class="code-viewer">
  <pre data-language="jQuery">
  $.ajax({
    url: 'http://api.myapp.com/books/3'
    type: 'PUT',
    data: {
      token: 'YOUR_APP_KEY',
      score: 5.0,
      title: "The Book Stealer"
    },
    success: function(data) {
      alert(data);
  });</pre>
</div>
