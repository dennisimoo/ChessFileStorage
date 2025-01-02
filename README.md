# Lichess Data Storage

This project allows you to upload text or image files, convert them into chess moves, and execute those moves on Lichess. Later, you can retrieve the file by reversing the process. Essentially, it's a way to store data on Lichess.

## Installation & Usage

1. **Prerequisites**  
   Ensure you have **Python 3.11** installed.

2. **Installation**  
   - Clone or download this repository.  
   - Navigate to the project directory in your terminal.  
   - Install the required dependencies by running:
     ```bash
     pip install -r requirements.txt
     ```

3. **Configuration**  
   1. **Create a `.env` File**  
      In your project directory, create a file named `.env`.

   2. **Add the Following Variables**  
      Copy and paste the template below into the `.env` file and replace the placeholders with your actual values:
      ```env
      LICHESS_BOT1_TOKEN=""
      LICHESS_BOT2_TOKEN=""
      LICHESS_BOT1_NAME=""
      LICHESS_BOT2_NAME=""
      ```

4. **Running the Project**  
   - Start the application by running:
     ```bash
     python app.py
     ```
   - The server will start on port 5000. Open [http://localhost:5000](http://localhost:5000) in your browser to begin testing.

## Special Thanks

A huge thanks to the **chessencryption** project by [WintrCat](https://github.com/WintrCat/chessencryption) for inspiring this idea. This project was created as an experiment to test the concept for myself.

You can also run this project through this website: [Lichess File Storage](https://lichessfilestorage.replit.app/).

**Note:** I recommend using `.txt` files for best results and faster speeds.
