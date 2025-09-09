# API Documentation

This document provides comprehensive API documentation for the Epstein Documents Browser.

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
- [Response Formats](#response-formats)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Examples](#examples)
- [SDK Examples](#sdk-examples)

## Overview

The Epstein Documents Browser provides a RESTful API for accessing document metadata, performing searches, and retrieving images. The API is designed to be simple, fast, and easy to integrate.

### Base URL

```
http://localhost:8080/api
```

### Content Types

- **Request**: `application/json`
- **Response**: `application/json`

## Authentication

Currently, the API does not require authentication for public endpoints. Future versions may include optional authentication for enhanced features.

## Endpoints

### Document Management

#### Get Document by ID

```http
GET /api/document/{id}
```

**Parameters:**
- `id` (integer, required): Document ID

**Response:**
```json
{
  "id": 1,
  "file_path": "Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00000001.tif",
  "filename": "DOJ-OGR-00000001.tif",
  "has_ocr_text": true,
  "ocr_text": "Sample OCR text content...",
  "file_size": 1024000,
  "created_at": "2025-09-08T12:00:00Z"
}
```

#### List Documents

```http
GET /api/documents
```

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page (default: 50, max: 100)
- `has_ocr` (boolean, optional): Filter by OCR availability
- `search` (string, optional): Search in filenames

**Response:**
```json
{
  "documents": [
    {
      "id": 1,
      "filename": "DOJ-OGR-00000001.tif",
      "has_ocr_text": true,
      "file_size": 1024000
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 33577,
    "pages": 672
  }
}
```

### Search

#### Search Documents

```http
GET /api/search
```

**Query Parameters:**
- `q` (string, required): Search query
- `type` (string, optional): Search type (`filename` or `content`, default: `content`)
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page (default: 20, max: 100)

**Response:**
```json
{
  "query": "juror",
  "results": [
    {
      "id": 123,
      "filename": "DOJ-OGR-00000123.jpg",
      "file_path": "Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00000123.jpg",
      "match_type": "content",
      "excerpt": "...prospective jurors completed a lengthy questionnaire...",
      "relevance_score": 0.95
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 45,
    "pages": 3
  },
  "search_time_ms": 150
}
```

#### Advanced Search

```http
POST /api/search/advanced
```

**Request Body:**
```json
{
  "query": "juror testimony",
  "filters": {
    "has_ocr": true,
    "file_types": ["jpg", "tif"],
    "date_range": {
      "start": "2025-01-01",
      "end": "2025-12-31"
    }
  },
  "options": {
    "fuzzy": true,
    "case_sensitive": false,
    "whole_words": false
  }
}
```

**Response:**
```json
{
  "query": "juror testimony",
  "filters_applied": {
    "has_ocr": true,
    "file_types": ["jpg", "tif"]
  },
  "results": [
    {
      "id": 123,
      "filename": "DOJ-OGR-00000123.jpg",
      "excerpt": "...juror testimony regarding the incident...",
      "relevance_score": 0.98,
      "highlights": ["juror", "testimony"]
    }
  ],
  "total": 23,
  "search_time_ms": 89
}
```

### Image Access

#### Get Image

```http
GET /api/image/{id}
```

**Parameters:**
- `id` (integer, required): Document ID

**Response:**
- **Content-Type**: `image/jpeg` or `image/tiff`
- **Body**: Binary image data

#### Get Thumbnail

```http
GET /api/thumbnail/{id}
```

**Parameters:**
- `id` (integer, required): Document ID
- `size` (string, optional): Thumbnail size (`small`, `medium`, `large`, default: `medium`)

**Response:**
- **Content-Type**: `image/jpeg`
- **Body**: Binary thumbnail data

### Statistics

#### Get System Statistics

```http
GET /api/stats
```

**Response:**
```json
{
  "total_documents": 33577,
  "documents_with_ocr": 33,
  "ocr_percentage": 0.1,
  "total_size_bytes": 17800000000,
  "database_size_bytes": 17000000,
  "last_updated": "2025-09-08T12:00:00Z",
  "processing_status": {
    "ocr_in_progress": false,
    "indexing_in_progress": false,
    "last_ocr_run": "2025-09-08T10:30:00Z"
  }
}
```

#### Get Processing Statistics

```http
GET /api/stats/processing
```

**Response:**
```json
{
  "ocr_stats": {
    "total_processed": 33,
    "successful": 30,
    "failed": 3,
    "average_processing_time_ms": 2500
  },
  "quality_stats": {
    "high_quality": 25,
    "medium_quality": 5,
    "low_quality": 3,
    "needs_review": 0
  },
  "recent_activity": [
    {
      "timestamp": "2025-09-08T12:00:00Z",
      "action": "ocr_completed",
      "document_id": 123,
      "status": "success"
    }
  ]
}
```

### Navigation

#### Get First Document

```http
GET /api/first-image
```

**Response:**
```json
{
  "id": 1,
  "filename": "DOJ-OGR-00000001.tif",
  "file_path": "Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00000001.tif"
}
```

#### Get Document Range

```http
GET /api/range
```

**Response:**
```json
{
  "first_id": 1,
  "last_id": 33577,
  "total_documents": 33577
}
```

#### Get Adjacent Documents

```http
GET /api/document/{id}/adjacent
```

**Parameters:**
- `id` (integer, required): Document ID

**Response:**
```json
{
  "current": {
    "id": 123,
    "filename": "DOJ-OGR-00000123.jpg"
  },
  "previous": {
    "id": 122,
    "filename": "DOJ-OGR-00000122.jpg"
  },
  "next": {
    "id": 124,
    "filename": "DOJ-OGR-00000124.jpg"
  }
}
```

## Response Formats

### Success Response

All successful API responses follow this format:

```json
{
  "status": "success",
  "data": {
    // Response data here
  },
  "meta": {
    "timestamp": "2025-09-08T12:00:00Z",
    "request_id": "req_123456789"
  }
}
```

### Error Response

All error responses follow this format:

```json
{
  "status": "error",
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document with ID 99999 not found",
    "details": {
      "document_id": 99999,
      "available_range": {
        "min": 1,
        "max": 33577
      }
    }
  },
  "meta": {
    "timestamp": "2025-09-08T12:00:00Z",
    "request_id": "req_123456789"
  }
}
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Error Codes

| Code | Description |
|------|-------------|
| `INVALID_PARAMETERS` | Invalid or missing parameters |
| `DOCUMENT_NOT_FOUND` | Document ID not found |
| `SEARCH_ERROR` | Search query failed |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `DATABASE_ERROR` | Database operation failed |
| `FILE_NOT_FOUND` | Image file not found |
| `OCR_NOT_AVAILABLE` | OCR text not available |

## Rate Limiting

The API implements rate limiting to ensure fair usage:

- **General API**: 1000 requests per hour per IP
- **Search API**: 100 requests per hour per IP
- **Image API**: 500 requests per hour per IP

### Rate Limit Headers

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1631026800
```

### Rate Limit Exceeded Response

```json
{
  "status": "error",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 3600 seconds.",
    "retry_after": 3600
  }
}
```

## Examples

### Python Examples

#### Basic Search

```python
import requests

# Search for documents
response = requests.get('http://localhost:8080/api/search', params={
    'q': 'juror',
    'type': 'content',
    'per_page': 10
})

data = response.json()
for result in data['results']:
    print(f"Document {result['id']}: {result['filename']}")
    print(f"Excerpt: {result['excerpt']}")
```

#### Download Image

```python
import requests

# Download image
response = requests.get('http://localhost:8080/api/image/123')

with open('document_123.jpg', 'wb') as f:
    f.write(response.content)
```

#### Advanced Search

```python
import requests

# Advanced search
search_data = {
    'query': 'testimony',
    'filters': {
        'has_ocr': True,
        'file_types': ['jpg']
    },
    'options': {
        'fuzzy': True,
        'case_sensitive': False
    }
}

response = requests.post(
    'http://localhost:8080/api/search/advanced',
    json=search_data
)

data = response.json()
print(f"Found {data['total']} results")
```

### JavaScript Examples

#### Fetch API

```javascript
// Search documents
async function searchDocuments(query) {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await response.json();
    return data.results;
}

// Get document details
async function getDocument(id) {
    const response = await fetch(`/api/document/${id}`);
    return await response.json();
}

// Usage
searchDocuments('juror').then(results => {
    results.forEach(result => {
        console.log(`Document ${result.id}: ${result.filename}`);
    });
});
```

#### jQuery Example

```javascript
// Search with jQuery
$.get('/api/search', { q: 'testimony', per_page: 20 })
    .done(function(data) {
        data.results.forEach(function(result) {
            $('#results').append(`
                <div class="result">
                    <h3>${result.filename}</h3>
                    <p>${result.excerpt}</p>
                </div>
            `);
        });
    });
```

### cURL Examples

#### Basic Search

```bash
curl "http://localhost:8080/api/search?q=juror&type=content&per_page=10"
```

#### Get Document

```bash
curl "http://localhost:8080/api/document/123"
```

#### Download Image

```bash
curl "http://localhost:8080/api/image/123" -o document_123.jpg
```

#### Advanced Search

```bash
curl -X POST "http://localhost:8080/api/search/advanced" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "testimony",
    "filters": {
      "has_ocr": true
    }
  }'
```

## SDK Examples

### Python SDK

```python
from epstein_browser import EpsteinBrowserClient

# Initialize client
client = EpsteinBrowserClient('http://localhost:8080')

# Search documents
results = client.search('juror', type='content', per_page=10)

# Get document details
document = client.get_document(123)

# Download image
image_data = client.get_image(123)

# Advanced search
results = client.advanced_search(
    query='testimony',
    filters={'has_ocr': True},
    options={'fuzzy': True}
)
```

### JavaScript SDK

```javascript
import { EpsteinBrowserClient } from 'epstein-browser-sdk';

// Initialize client
const client = new EpsteinBrowserClient('http://localhost:8080');

// Search documents
const results = await client.search('juror', {
    type: 'content',
    perPage: 10
});

// Get document details
const document = await client.getDocument(123);

// Download image
const imageBlob = await client.getImage(123);
```

## Webhooks

### Webhook Events

The API supports webhooks for real-time notifications:

- `document.processed`: Document OCR processing completed
- `document.indexed`: Document added to search index
- `search.performed`: Search query executed
- `error.occurred`: System error occurred

### Webhook Configuration

```http
POST /api/webhooks
```

**Request Body:**
```json
{
  "url": "https://your-app.com/webhooks/epstein-browser",
  "events": ["document.processed", "search.performed"],
  "secret": "your-webhook-secret"
}
```

### Webhook Payload

```json
{
  "event": "document.processed",
  "timestamp": "2025-09-08T12:00:00Z",
  "data": {
    "document_id": 123,
    "filename": "DOJ-OGR-00000123.jpg",
    "status": "success",
    "processing_time_ms": 2500
  }
}
```

## Changelog

### Version 1.0.0 (2025-09-08)

- Initial API release
- Document management endpoints
- Search functionality
- Image access
- Statistics and monitoring
- Rate limiting
- Error handling

---

*This API documentation is automatically generated and updated with each release. For the latest information, always refer to the current version.*
