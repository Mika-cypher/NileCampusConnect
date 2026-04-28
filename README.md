# NileCampusConnect | Hyper-Local Student Freelance Marketplace

**NileCampusConnect** is a web-based platform designed exclusively for the Nile University of Nigeria community. It bridges the gap between students with marketable skills (design, coding, writing) and members of the campus community who need services, creating a safe, closed-loop freelance economy.

## 🎯 Problem Statement

In the university ecosystem, many students possess valuable skills but lack a centralized, trusted platform to monetize them. Conversely, students and organizations often look for affordable services but struggle to find reliable talent on campus. NileCampusConnect solves this by providing a verified marketplace for the university demographic.

## ⚡ Key Features

- **Service Listings:** Students can post "Gigs" .
- **Smart Search & Filtering:** Users can filter services by category, price range, and delivery time.
- **User Profiles:** dedicated profiles showcasing skills, portfolios, and ratings from previous campus gigs.
- **Secure Authentication:** System designed to verify student status within the university network.

## 🛠️ Tech Stack

- **Backend:** Python (Django Framework) - chosen for its robust security and rapid development capabilities.
- **Frontend:** HTML5, CSS3, JavaScript (Bootstrap/Tailwind).
- **Database:** SQLite (Development) / PostgreSQL (Production).
- **Architecture:** Model-View-Template (MVT).

## 🚀 Getting Started

To run the project locally for development and testing:

```bash
# Step 1: Clone the repository
git clone https://github.com/Mika-cypher/NileCampusConnect.git

# Step 2: Create a virtual environment
python -m venv venv

# Step 3: Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Step 4: Install dependencies
pip install -r requirements.txt

# Step 5: Apply migrations
python manage.py migrate

# Step 6: Run the server
python manage.py runserver

Future Roadmap
In-App Messaging: Real-time chat between buyers and sellers.

Escrow Payment System: Integration with local payment gateways (Paystack/Flutterwave) to hold funds until service delivery.

Developed by Kono Michael Achua as a Final Year Project for the Department of Computer Science, Nile University of Nigeria.