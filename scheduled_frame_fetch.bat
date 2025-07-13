@echo off
call C:\Users\Flynn\Documents\smoke_cast_back\env\Scripts\activate.bat


echo [%time%] Running Script 1...
python C:\Users\Flynn\Documents\smoke_cast_back\get_frames.py
echo Script 1 done. Exit code: %errorlevel% 

echo [%time%] Running Script 2...
python C:\Users\Flynn\Documents\smoke_cast_back\get_frames.py full
echo Script 2 done. Exit code: %errorlevel% 


echo [%time%] Deactivating...
deactivate

 
