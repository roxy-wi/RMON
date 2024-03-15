import psutil

import app.modules.server.server as server_mod


def show_ram_metrics(metrics_type: str) -> dict:
    metrics = {'chartData': {}}
    rams = ''

    if metrics_type == '1':
        rams_list = psutil.virtual_memory()
        rams += str(round(rams_list.total / 1048576, 2)) + ' '
        rams += str(round(rams_list.used / 1048576, 2)) + ' '
        rams += str(round(rams_list.free / 1048576, 2)) + ' '
        rams += str(round(rams_list.shared / 1048576, 2)) + ' '
        rams += str(round(rams_list.cached / 1048576, 2)) + ' '
        rams += str(round(rams_list.available / 1048576, 2)) + ' '
    else:
        commands = ["free -m |grep Mem |awk '{print $2,$3,$4,$5,$6,$7}'"]
        metric, error = server_mod.subprocess_execute(commands[0])

        for i in metric:
            rams = i

    metrics['chartData']['rams'] = rams

    return metrics


def show_cpu_metrics(metrics_type: str) -> dict:
    metrics = {'chartData': {}}
    cpus = ''

    if metrics_type == '1':
        cpus_list = psutil.cpu_times_percent(interval=1, percpu=False)
        cpus += str(cpus_list.user) + ' '
        cpus += str(cpus_list.system) + ' '
        cpus += str(cpus_list.nice) + ' '
        cpus += str(cpus_list.idle) + ' '
        cpus += str(cpus_list.iowait) + ' '
        cpus += str(cpus_list.irq) + ' '
        cpus += str(cpus_list.softirq) + ' '
        cpus += str(cpus_list.steal) + ' '
    else:
        commands = [
            "top -b -n 1 |grep Cpu |awk -F':' '{print $2}'|awk  -F' ' 'BEGIN{ORS=\" \";} { for (i=1;i<=NF;i+=2) print $i}'"]
        metric, error = server_mod.subprocess_execute(commands[0])

        for i in metric:
            cpus = i

    metrics['chartData']['cpus'] = cpus

    return metrics
