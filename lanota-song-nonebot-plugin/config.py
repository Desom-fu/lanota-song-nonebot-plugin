from pathlib import Path

lanota_group = 1037559220
save_dir = Path("Data") / "generate_image" 
backup_path = Path() / "Data" / "UserList_Backup"
user_path = Path() / "Data" / "UserList"
file_name = "UserData.json"
full_path = user_path / file_name
font_path = Path("Data") / "fonts.ttf"
lanota_data_path = Path() / "Data" / "LanotaSongList"
lanota_file_name = "song_list.json"
lanota_alias_name = "song_alias.json"
lanota_alias_full_path = lanota_data_path / lanota_alias_name
lanota_full_path = lanota_data_path / lanota_file_name