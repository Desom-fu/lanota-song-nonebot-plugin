from pathlib import Path

lanota_group = 114514  # 这里不用管，已然废弃，填什么都行
allowed_groups = {1037559220, 551374760, 565752728, 1006108282, 1034528298}  # 白名单群组，只有这些群才会触发
allowed_users = {"121096913","2946244126","3631828847","2976143542"}  # 添加允许的私聊用户QQ号
save_dir = Path("Data") / "generate_image" 
backup_path = Path("Data") / "UserList_Backup"
user_path = Path("Data") / "UserList"
file_name = "UserData.json"
full_path = user_path / file_name
font_path = Path("Data") / "fonts.ttf"
lanota_data_path = Path("Data") / "LanotaSongList"
lanota_file_name = "song_list.json"
lanota_alias_name = "song_alias.json"
lanota_table_name = "song_table.json"
lanota_table_full_path = lanota_data_path / lanota_table_name
lanota_alias_full_path = lanota_data_path / lanota_alias_name
lanota_full_path = lanota_data_path / lanota_file_name