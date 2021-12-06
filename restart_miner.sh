pssh -i -h restart.hosts 'sudo systemctl stop aleod-miner'
pssh -i -h restart.hosts 'sudo rm -rf /root/.aleo/storage/ledger-2'
pssh -i -h restart.hosts 'sudo systemctl start aleod-miner'
