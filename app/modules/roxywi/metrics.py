import psutil

import app.modules.server.server as server_mod


def show_ram_metrics(server_ip: str) -> dict:
    metrics = {'chartData': {}}
    rams = ''

    if str(server_ip) == '127.0.0.1':
        rams_list = psutil.virtual_memory()
        for i in (rams_list.used, rams_list.free, rams_list.shared, rams_list.cached, rams_list.available, rams_list.total):
            rams += str(round(i / 1048576, 2)) + ' '
    else:
        commands = "sudo free -m |grep Mem |awk '{print $3,$4,$5,$6,$7,$2}'"
        rams = server_mod.ssh_command(server_ip, commands).replace('\r', '').replace('\n', '')

    metrics['chartData']['rams'] = rams

    return metrics


def show_cpu_metrics(server_ip: str) -> dict:
    metrics = {'chartData': {}}
    cpus = ''
    if str(server_ip) == '127.0.0.1':
        total = psutil.cpu_percent(0.5)
        cpus_list = psutil.cpu_times_percent(interval=0.5, percpu=False)
        for i in (cpus_list.user, cpus_list.system, cpus_list.nice, cpus_list.idle, cpus_list.iowait, cpus_list.irq, cpus_list.softirq, cpus_list.steal):
            cpus += str(round(i, 2)) + ' '
        cpus += str(total) + ' '
    else:
        cmd = "top -d 0.5 -b -n2 | grep 'Cpu(s)'|tail -n 1 | awk '{print $2 + $4}'"
        total = server_mod.ssh_command(server_ip, cmd).replace('\r', '').replace('\n', '')
        cmd = "sudo top -b -n 1 |grep Cpu |awk -F':' '{print $2}'|awk -F' ' 'BEGIN{ORS=\" \";} { for (i=1;i<=NF;i+=2) print $i}'"
        cpus = server_mod.ssh_command(server_ip, cmd)
        cpus += total

    metrics['chartData']['cpus'] = cpus

    return metrics
