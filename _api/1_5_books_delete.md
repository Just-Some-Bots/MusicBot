---
title: /books/:id
type: delete
description: Deletes a book
right_code:
  response: |
    {
      "id": 3,
      "status": "deleted"
    }
---
Deletes a book in your collection.

<div class="code-viewer">
  <pre data-language="jQuery">
  $.ajax({
    url: 'http://api.myapp.com/books/3'
    type: 'DELETE',
    data: {
      token: 'YOUR_APP_KEY'
    },
    success: function(data) {
      alert(data);
  });</pre>
</div>
