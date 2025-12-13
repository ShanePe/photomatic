# Photomatic 📸

A simple, lightweight **Flask-based random photo slideshow web application**.  
Photomatic serves images from a local directory and displays them in a fullscreen, responsive slideshow with automatic transitions.

---

## ✨ Features

- Random photo selection using reservoir sampling
- Web-based slideshow with smooth fade transitions every 30 seconds
- Responsive fullscreen design that adapts to any device
- HEIC support: converts HEIC images to JPEG on the fly
- Multiple formats supported: JPG, JPEG, PNG, GIF, WebP
- Overlay text option for captions or watermarks
- Caching and compression to reduce bandwidth and improve performance

---

## 🚀 Installation

1. Clone the repository:
   git clone https://github.com/ShanePe/photomatic.git
   cd photomatic

2. Install dependencies:
   pip install flask pillow pillow-heif

3. Ensure you have Python 3.6+ installed.

---

## ▶️ Usage

Run the application with:

python app/app.py --photos /path/to/your/photos --port 5000

Arguments:

- --photos: Required. Path to the base folder containing your images
- --port: Optional. Port to run the server on (default: 5000)

Open your browser at:  
http://localhost:5000

---

## 🐳 Docker Support

You can also run Photomatic inside a Docker container.

Dockerfile (create in project root):

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app/app.py", "--photos", "/photos", "--port", "5000"]

requirements.txt:
flask
pillow
pillow-heif

Build & Run:
docker build -t photomatic .
docker run -p 5000:5000 -v /path/to/photos:/photos photomatic

Then open http://localhost:5000

---

## 📂 Project Structure

photomatic/
├── app/ # Flask app source code
├── README.md # Project documentation
├── .gitignore # Git ignore rules

---

## 🛠 Requirements

- Python 3.6+
- Flask
- Pillow
- pillow-heif (for HEIC support)

---

## 🌟 Roadmap / Ideas

- Add configuration for slideshow interval
- Support remote image sources (e.g., S3, Google Drive)
- Add keyboard controls (pause, next, previous)
- Dockerfile for containerized deployment

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you’d like to change.

---

## 📜 License

This project is licensed under the MIT License – see the LICENSE file for details.
