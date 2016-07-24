# Aviator

API documentation template for Jekyll. Browse through a [live demo](#TODO).
Start documenting your API with this configurable theme.

![Aviator template screenshot](images/_screenshot.png)

Aviator was made by [CloudCannon](http://cloudcannon.com/), the Cloud CMS for Jekyll.
Find more templates and themes at [Jekyll Tips](http://jekyll.tips/templates/).

Learn Jekyll with step-by-step tutorials and videos at [Jekyll Tips](http://jekyll.tips/).

## Features

* Three column layout
* Fully responsive 
* Full text search
* Pre-styled components
* Auto-generated navigation based on category
* Optimised for editing in [CloudCannon](http://cloudcannon.com/)
* SEO tags
* Google Analytics

## Setup

1. Add your site and author details in `_config.yml`.
2. Get a workflow going to see your site's output (with [CloudCannon](https://app.cloudcannon.com/) or Jekyll locally).

## Develop

Aviator was built with [Jekyll](http://jekyllrb.com/) version 3.1.6, but should support newer versions as well.

Install the dependencies with [Bundler](http://bundler.io/):

~~~bash
$ bundle install
~~~

Run `jekyll` commands through Bundler to ensure you're using the right versions:

~~~bash
$ bundle exec jekyll serve
~~~

## Editing

Aviator is already optimised for adding, updating and removing documentation pages in CloudCannon.

### Usage

* Each section is a different collection, this helps organise your content.
* Set the order of the collections with the position field in collection configuration in `_config.yml`.
* Set the order of the documents inside a collection by setting the position in front matter.

### Search

* Add `excluded_in_search: true` to any documentation page's front matter to exclude that page in the search results.
