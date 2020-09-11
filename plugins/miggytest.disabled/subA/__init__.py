class subA:
    def __init__(self, logger):
        self.logger = logger

    def ping(cls):
        cls.logger.info('ping!')
