var cur_url = window.location.href.split('/').pop();
cur_url = cur_url.split('/');
function showOverview(serv, hostnamea) {
	showOverviewHapWI();
	showUsersOverview();
	showSubOverview();
	showServicesOverview();
	updatingCpuRamCharts();
	var i;
	for (i = 0; i < serv.length; i++) {
		showOverviewCallBack(serv[i], hostnamea[i])
	}
}
function showOverviewCallBack(serv, hostnamea) {
	$.ajax( {
		url: "/overview/server/"+serv,
		beforeSend: function() {
			$("#"+hostnamea).html('<img class="loading_small" src="/app/static/images/loading.gif" />');
		},
		type: "GET",
		success: function( data ) {
			if (data.indexOf('error:') != '-1') {
				toastr.error(data);
				$("#"+hostnamea).html("");
			} else {
				$("#" + hostnamea).empty();
				$("#" + hostnamea).html(data);
			}
		}
	} );
}
function showServicesOverview() {
	$.ajax( {
		url: "/overview/services",
		beforeSend: function() {
			$("#services_ovw").html('<img class="loading_small_bin_bout" style="padding-left: 100%;padding-top: 40px;padding-bottom: 40px;" src="/static/images/loading.gif" />');

		},
		type: "GET",
		success: function( data ) {
			if (data.indexOf('error:') != '-1') {
				toastr.error(data);
			} else {
				$("#services_ovw").empty();
				$("#services_ovw").html(data);
			}
		}
	} );
}
function showOverviewServer(name, ip, id, service) {
	$.ajax( {
		url: "/service/cpu-ram-metrics/" + ip + "/" + id + "/" + name + "/" + service,
		success: function( data ) {
			if (data.indexOf('error:') != '-1') {
				toastr.error(data);
			} else {
				$("#ajax-server-" + id).empty();
				$("#ajax-server-" + id).css('display', 'block');
				$("#ajax-server-" + id).css('background-color', '#fbfbfb');
				$("#ajax-server-" + id).css('border', '1px solid #A4C7F5');
				$(".ajax-server").css('display', 'block');
				$(".div-server").css('clear', 'both');
				$(".div-pannel").css('clear', 'both');
				$(".div-pannel").css('display', 'block');
				$(".div-pannel").css('padding-top', '10px');
				$(".div-pannel").css('height', '70px');
				$("#div-pannel-" + id).insertBefore('#up-pannel')
				$("#ajax-server-" + id).html(data);
				$.getScript("/static/js/fontawesome.min.js")
				getChartDataHapWiRam()
				getChartDataHapWiCpu()
			}
		}					
	} );
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

	$( "#show-all-haproxy-wi-log" ).click( function() {
		$(".show-haproxy-wi-log").show("fast");
		$("#hide-all-haproxy-wi-log").css("display", "block");
		$("#show-all-haproxy-wi-log").css("display", "none");
	});
	$( "#hide-all-haproxy-wi-log" ).click( function() {
		$(".show-haproxy-wi-log").hide("fast");
		$("#hide-all-haproxy-wi-log").css("display", "none");
		$("#show-all-haproxy-wi-log").css("display", "block");
	});

	if (cur_url[0] == "" || cur_url[0] == "waf" || cur_url[0] == "metrics") {
		$('#secIntervals').css('display', 'none');
	}
});
function showUsersOverview() {
	$.ajax( {
		url: "overview/users",
		type: "GET",
		beforeSend: function() {
			$("#users-table").html('<img class="loading_small_bin_bout" style="padding-left: 100%;padding-top: 40px;padding-bottom: 40px;" src="/static/images/loading.gif" />');
		},
		success: function( data ) {
			data = data.replace(/\s+/g,' ');
			if (data.indexOf('error:') != '-1') {
				toastr.error(data);
			} else {
				$("#users-table").html(data);
			}
		}
	} );
}
function showSubOverview() {
	$.ajax( {
		url: "/overview/sub",
		type: "GET",
		beforeSend: function() {
			$("#sub-table").html('<img class="loading_small_bin_bout" style="padding-left: 40%;padding-top: 40px;padding-bottom: 40px;" src="/static/images/loading.gif" />');
		},
		success: function( data ) {
			data = data.replace(/\s+/g,' ');
			if (data.indexOf('error:') != '-1') {
				toastr.error(data);
			} else {
				$("#sub-table").html(data);
			}
		}
	} );
}

function ShowOverviewLogs() {
	$.ajax( {
		url: "/overview/logs",
		type: "GET",
		beforeSend: function() {
			$("#overview-logs").html('<img class="loading_small_bin_bout" style="padding-left: 40%;padding-top: 40px;padding-bottom: 40px;" src="/static/images/loading.gif" />');
		},
		success: function( data ) {
			data = data.replace(/\s+/g,' ');
			$("#overview-logs").html(data);
			$.getScript("/static/js/fontawesome.min.js")
			$.getScript("/static/js/overview.js")
		}
	} );
}
