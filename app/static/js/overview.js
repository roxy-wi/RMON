var cur_url = window.location.href.split('/').pop();
cur_url = cur_url.split('/');
function showOverview(serv, hostnamea) {
	showOverviewHapWI();
	showUsersOverview();
	showSubOverview();
	showServicesOverview();
	var i;
	for (i = 0; i < serv.length; i++) {
		showOverviewCallBack(serv[i], hostnamea[i])
	}
}
function showOverviewCallBack(serv, hostnamea) {
    return RmonUI.loadFragment("#" + hostnamea, "/overview/server/" + encodeURIComponent(serv));
}
function showServicesOverview() {
    return RmonUI.loadFragment("#services_ovw", "/overview/services");
}
function showOverviewServer(ip) {
	getChartDataHapWiRam(ip);
	getChartDataHapWiCpu(ip);
}
$( function() {
	try {
		if (cur_url[0] == '') {
			UsersShowIntervalId = setInterval(showUsersOverview, 600000);
			$(window).focus(function () {
				UsersShowIntervalId = setInterval(showUsersOverview, 600000);
			});
			$(window).blur(function () {
				clearInterval(UsersShowIntervalId);
			});
		}
	} catch (e) {
		console.log(e);
	}
	$( "#show-all-users" ).click( function() {
		$(".show-users").show("fast");
		$("#hide-all-users").css("display", "block");
		$("#show-all-users").css("display", "none");
	});
	$("#hide-all-users").click(function() {
		$(".show-users").hide("fast");
		$("#hide-all-users").css("display", "none");
		$("#show-all-users").css("display", "block");
	});

	$( "#show-all-groups" ).click( function() {
		$(".show-groups").show("fast");
		$("#hide-all-groups").css("display", "block");
		$("#show-all-groups").css("display", "none");
	});
	$( "#hide-all-groups" ).click( function() {
		$(".show-groups").hide("fast");
		$("#hide-all-groups").css("display", "none");
		$("#show-all-groups").css("display", "block");
	});

	$(document).on('click', '#show-all-haproxy-wi-log', function() {
		$(".show-haproxy-wi-log").show("fast");
		$("#hide-all-haproxy-wi-log").css("display", "block");
		$("#show-all-haproxy-wi-log").css("display", "none");
	});
	$(document).on('click', '#hide-all-haproxy-wi-log', function() {
		$(".show-haproxy-wi-log").hide("fast");
		$("#hide-all-haproxy-wi-log").css("display", "none");
		$("#show-all-haproxy-wi-log").css("display", "block");
	});

	if (cur_url[0] == "" || cur_url[0] == "waf" || cur_url[0] == "metrics") {
		$('#secIntervals').css('display', 'none');
	}
});
function showUsersOverview() {
    return RmonUI.loadFragment("#users-table", "/overview/users");
}
function showSubOverview() {
    return RmonUI.loadFragment("#sub-table", "/overview/sub");
}
function ShowOverviewLogs() {
    return RmonUI.loadFragment("#overview-logs", "/overview/logs");
}
