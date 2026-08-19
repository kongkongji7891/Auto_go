import configparser
import logging
import pathlib

logger = logging.getLogger(__name__)

class ag_cofig:
    def __init__():
        cofig_name = f"cofig.ini"
        self.cofig_path = pathlib.Path(__file__).resolve().parent / cofig_name

        self.config = configparser.ConfigParser()
        self.config.read(self.cofig_path)

        if config.has_section('kataGO_pth') and config.has_option('kataGO_pth', 'exe') and config.has_option('kataGO_pth', 'model') and config.has_option('kataGO_pth', 'cfg') and config.has_option('kataGO_set', 'MaxVisit'):
            pass
    def get_katago_path():
        return self.config['kataGO_pth']['exe']
    def get_katago_mod_path():
        return self.config['kataGO_pth']['model']
    def get_katago_cfg_path():
        return self.config['kataGO_pth']['cfg']
    def get_katago_mv():
        return config.getint('kataGO_set','MaxVisit')
    def set_katago_path(pth:str):
        self.config['kataGO_pth']['exe'] = pth
    def set_katago_mod_path(pth:str):
        self.config['kataGO_pth']['model'] = pth
    def set_katago_cfg_path(pth:str):
        self.config['kataGO_pth']['cfg'] = pth
    def set_katago_mv(mv:int):
        self.config['kataGO_set']['MaxVisit'] = mv
    def sava_cofig():
        with open(self.cofig_path, 'w', encoding='utf-8') as f:
            config.write(f)
    def read_cofig():
        config.read(self.cofig_path)