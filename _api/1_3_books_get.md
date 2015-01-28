---
title: /books/:id
type: get
description: Get Book
right_code:
  response: |
    {
      "id": 3,
      "title": "The Book Thief",
      "score": 4.3,
      "date_added": "5/1/2015"
    }
---

Returns a specific book from your collection

<div class="code-viewer">
  <pre data-language="jQuery">
  $.get('http://api.myapp.com/books/3', {
    token: 'YOUR_APP_KEY',
  }, function(data) {
    alert(data);
  });</pre>
</div>
