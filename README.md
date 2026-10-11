# Bahay Pahinga Stays: Airbnb Reservation System

## Business
A small family-run Airbnb with three units (Garden Studio, Family Loft, Barkada Villa). Guests use the site to reserve; the host (admin) manages all bookings.

## Problem solved
The host used to take bookings through chat messages and often double-booked rooms. This system checks availability automatically, computes the total price, and keeps all bookings in one place.

## Features
- **Landing page:** business info, room list with prices, image, "Book Now" button, mobile-friendly.
- **Users:** register, login, logout, hashed passwords (Werkzeug), protected pages, roles (admin / guest).
- **CRUD (Reservations):** create, view, edit, delete with confirmation; validation (valid dates, no past dates, guest capacity, no overlapping bookings); data saved in SQLite.
- **Roles:** guests only see and edit their own reservations; admin sees and manages all.

## Tech stack
Python 3, Flask, SQLite, Jinja templates, plain CSS.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. The database (`stays.db`) and sample data are created on first run.
Optional: set a `SECRET_KEY` environment variable for production.

## Test accounts
| Role  | Email            | Password |
|-------|------------------|----------|
| Admin | admin@stay.test  | admin123 |
| Guest | guest@stay.test  | guest123 |

## AI tools used
- Claude AI to help me organize the codes and some errors that are found

## Idea claim 
**Bahay Pahinga Stays: online reservations for a small Airbnb host: Reservations**
