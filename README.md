# Image-Processing

To start the program just use **python main.py**<br>
You will need to download some libraries to run main.py just google it and you will get it

I have attached a file for you refrence in the code<br>
Now to send request you can use the curl method, Use the following command<br>
curl -X POST -F "file=@sample_test.csv" http://127.0.0.1:5000/upload<br>

Now if you have to use webhooks then use this command<br>
curl -X POST -F "file=@sample_test.csv" -F "webhook_url=https://example.com/webhook" http://127.0.0.1:5000/upload<br>

Similarly, if you want to check the status then use this command<br>
curl -X GET http://127.0.0.1:5000/status/<request_id><br>
