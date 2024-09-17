function getAgentsForRegion(region_id) {
	$.ajax({
		url: api_v_prefix + "/rmon/agents",
		type: "get",
		contentType: "application/json; charset=UTF-8",
		async: false,
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data.error);
			} else {
				for (let k in data) {
                    let agent = data[k];
                    if (agent.enabled === 1 && !agent.region_id) {
                        removeCheckFromStatus(agent.id, agent.name);
                    }
                    if (agent.enabled === 1 && Number(agent.region_id) === Number(region_id)) {
                        addCheckToStatus(agent.id, agent.name);
                    }
                }
			}
		}
	});
}
function addRegionDialog(agent_id=0, edit=false) {
    cleanRegionAddForm();
    let tabel_title = $("#add-region-page-overview").attr('title');
    let buttons = [];
    getAgentsForRegion(agent_id);
    if (edit) {
        add_word = translate_div.attr('data-edit');
        tabel_title = $("#add-region-page-overview").attr('data-edit');
        getRegionSettings(agent_id);
        buttons = [{
            text: add_word,
            click: function () {
                addRegion($(this), agent_id, true);
            }
        }, {
            text: cancel_word,
            click: function () {
                $(this).dialog("close");
            }
        }]
    } else {
        buttons = [{
            text: add_word,
            click: function () {
                addRegion($(this));
            }
        }, {
            text: cancel_word,
            click: function () {
                $(this).dialog("close");
            }
        }]
    }
    let dialogTable = $("#add-region-page").dialog({
        autoOpen: false,
        resizable: false,
        height: "auto",
        width: 630,
        modal: true,
        title: tabel_title,
        show: {
            effect: "fade",
            duration: 200
        },
        hide: {
            effect: "fade",
            duration: 200
        },
        buttons: buttons
    });
    dialogTable.dialog('open');
}
function addRegion(dialog_id, region_id=0, edit=false) {
    let valid = true;
    let name = $('#new-region-name');
    let desc = $('#new-region-desc').val();
    let allFields = $([]).add(name);
    allFields.removeClass("ui-state-error");
    valid = valid && checkLength(name, "Name", 1);
    let enabled = $('#new-region-enabled').is(':checked') ? 1 : 0;
    let shared = $('#new-region-shared').is(':checked') ? 1 : 0;
    let json_data = {
        'name': name.val(),
        'description': desc,
        'enabled': enabled,
        'shared': shared
    };
    json_data['agents'] = createJsonRegion('#checked-agents div');
    let method = 'POST';
    let req_url = api_v_prefix + "/rmon/region";
    if (edit) {
        method = 'PUT'
        req_url = api_v_prefix + "/rmon/region/" + region_id;
    }
    if (valid) {
        $.ajax({
            url: req_url,
            type: method,
            data: JSON.stringify(json_data),
            contentType: "application/json; charset=utf-8",
            success: function (data) {
                if (data.status === 'failed') {
                    toastr.error(data.error);
                } else {
                    toastr.clear();
                    $(dialog_id).dialog("close");
                    if (edit) {
                        getRegion(region_id, false);
                    } else {
                        getRegion(data.id, new_agent = true);
                    }
                }
            }
        });
    }
}
function addCheckToStatus(server_id, hostname) {
	let service_word = translate_div.attr('data-service');
	let html_tag = '<div id="remove_check-' + server_id + '" data-name="' + hostname + '">' +
		'<div class="check-name">' + hostname + '</div>' +
		'<div class="add_user_group check-button" onclick="removeCheckFromStatus(' + server_id + ', \'' + hostname + '\')" title="' + delete_word + ' ' + service_word + '">-</div>' +
		'</div>';
	$('#add_check-' + server_id).remove();
	$("#checked-agents").append(html_tag);
}
function removeCheckFromStatus(server_id, hostname) {
	let add_word = translate_div.attr('data-add');
	let service_word = translate_div.attr('data-service');

	let html_tag = '<div class="all-checks" id="add_check-' + server_id + '" data-name="' + hostname + '">' +
		'<div class="check-name">' + hostname + '</div>' +
		'<div class="add_user_group check-button" onclick="addCheckToStatus(' + server_id + ',  \'' + hostname + '\')" title="' + add_word + ' ' + service_word + '">+</div></div>';
    $("#all-agents").append(html_tag);
	$('#remove_check-' + server_id).remove();
}
function createJsonRegion(div_id) {
    let jsonData = [];
    $(div_id).each(function () {
        if ($(this).attr('data-name')) {
            let this_id = $(this).attr('id').split('-')[1];
            jsonData.push(this_id);
        }
    });
    return jsonData;
}
function getRegionSettings(agent_id) {
	$.ajax({
		url: api_v_prefix + "/rmon/region/" + agent_id,
		async: false,
		success: function (data) {
			$('#new-region-name').val(data['name'].replaceAll("'", ""));
			$('#new-regin-desc').val(data['description'].replaceAll("'", ""));
			$('#new-regin-enabled').checkboxradio("refresh");
			if (data['enabled'] == '1') {
				$('#new-regin-enabled').prop('checked', true)
			} else {
				$('#new-region-enabled').prop('checked', false)
			}
			if (data['shared'] == '1') {
				$('#new-region-shared').prop('checked', true)
			} else {
				$('#new-region-shared').prop('checked', false)
			}
			$('#new-region-enabled').checkboxradio("refresh");
			$('#new-region-shared').checkboxradio("refresh");
		}
	});
}
function getRegion(agent_id, new_region=false) {
	$.ajax({
		url: "/rmon/region/info/" + agent_id,
		success: function (data) {
			data = data.replace(/^\s+|\s+$/g, '');
			if (data.indexOf('error:') != '-1') {
				toastr.error(data);
			} else {
				if (new_region) {
					$('#regions').append(data);
				} else {
					$('#region-' + agent_id).replaceWith(data);
				}
				$.getScript("/static/js/fontawesome.min.js");
				$('#region-' + agent_id).removeClass('animated-background');
			}
		}
	});
}
function getRegions(select_id) {
	$.ajax({
		url: api_v_prefix + "/rmon/regions",
		type: "get",
		contentType: "application/json; charset=UTF-8",
		async: false,
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data.error);
			} else {
				toastr.clear();
				$(select_id).find('option').remove();
				$(select_id).append('<option value="" selected disabled>------</option>');
				for (k in data) {
					let agent = data[k];
					if (agent.enabled === 1) {
						$(select_id).append('<option value="' + agent.id + '">' + agent.name.replaceAll("'", "") + '</option>');
					}
				}
				$(select_id).selectmenu('refresh');
			}
		}
	});
}
function confirmDeleteRegion(id) {
	$( "#dialog-confirm" ).dialog({
		resizable: false,
		height: "auto",
		width: 400,
		modal: true,
		title: delete_word+" " +$('#region-name-'+id).text() + "?",
		buttons: [{
			text: delete_word,
			click: function () {
				$(this).dialog("close");
				removeRegion(id, $(this));
			}
		}, {
			text: cancel_word,
			click: function() {
				$( this ).dialog( "close" );
			}
		}]
	});
}
function removeRegion(id, dialog_id) {
	$.ajax({
        url: api_v_prefix + "/rmon/region/" + id,
        type: "delete",
        data: JSON.stringify({}),
		contentType: "application/json; charset=utf-8",
		statusCode: {
			204: function (xhr) {
				toastr.clear();
                $(dialog_id).dialog("close");
				$('#region-'+id).remove();
			},
			404: function (xhr) {
				toastr.clear();
                $(dialog_id).dialog("close");
				$('#region-'+id).remove();
			}
		},
		success: function (data) {
			if (data) {
				if (data.status === "failed") {
					toastr.error(data.error);
				}
			}
		}
    });
}
function cleanRegionAddForm() {
	$('#new-region-name').val('');
	$('#new-regin-desc').val('');
	$('#new-agent-shared').prop('checked', false);
	$('#new-agent-enabled').prop('checked', true);
	$('#new-agent-shared').checkboxradio("refresh");
	$('#new-agent-enabled').checkboxradio("refresh");
	$('#checked-agents').html('');
	$('#all-agents').html('');
}
