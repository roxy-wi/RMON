function getRegionsForCountry(country_id) {
	$.ajax({
		url: api_v_prefix + "/rmon/regions",
		type: "get",
		contentType: "application/json; charset=UTF-8",
		async: false,
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data.error);
			} else {
				for (let k in data) {
                    let agent = data[k];
                    if (agent.enabled && !agent.country_id) {
                        removeRegionFromStatus(agent.id, agent.name);
                    }
                    if (agent.enabled && agent.country_id != null && Number(agent.country_id) === Number(country_id)) {
                        addRegionToStatus(agent.id, agent.name);
                    }
                }
			}
		}
	});
}
function addCountryDialog(agent_id=0, edit=false) {
    cleanCountryAddForm();
    let tabel_title = $("#add-country-page-overview").attr('title');
    let buttons = [];
    getRegionsForCountry(agent_id);
    if (edit) {
        add_word = translate_div.attr('data-edit');
        tabel_title = $("#add-country-page-overview").attr('data-edit');
        getCountrySettings(agent_id);
        buttons = [{
            text: add_word,
            click: function () {
                addCountry($(this), agent_id, true);
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
                addCountry($(this));
            }
        }, {
            text: cancel_word,
            click: function () {
                $(this).dialog("close");
            }
        }]
    }
    let dialogTable = $("#add-country-page").dialog({
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
function addCountry(dialog_id, country_id=0, edit=false) {
    let valid = true;
    let name = $('#new-country-name');
    let desc = $('#new-country-desc').val();
    let allFields = $([]).add(name);
    allFields.removeClass("ui-state-error");
    valid = valid && checkLength(name, "Name", 1);
    let enabled = $('#new-country-enabled').is(':checked') ? 1 : 0;
    let shared = $('#new-country-shared').is(':checked') ? 1 : 0;
    let json_data = {
        'name': name.val(),
        'description': desc,
        'enabled': enabled,
        'shared': shared
    };
    json_data['regions'] = createJsonCountry('#checked-regions div');
    let method = 'POST';
    let req_url = api_v_prefix + "/rmon/country";
    if (edit) {
        method = 'PUT'
        req_url = api_v_prefix + "/rmon/country/" + country_id;
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
                        getCountry(country_id, false);
                    } else {
                        getCountry(data.id, new_agent = true);
                    }
                }
            }
        });
    }
}
function addRegionToStatus(server_id, hostname) {
	let service_word = translate_div.attr('data-service');
	let html_tag = '<div id="remove_check-' + server_id + '" data-name="' + hostname + '">' +
		'<div class="check-name">' + hostname + '</div>' +
		'<div class="add_user_group check-button" onclick="removeRegionFromStatus(' + server_id + ', \'' + hostname + '\')" title="' + delete_word + ' ' + service_word + '">-</div>' +
		'</div>';
	$('#add_check-' + server_id).remove();
	$("#checked-regions").append(html_tag);
}
function removeRegionFromStatus(server_id, hostname) {
	let add_word = translate_div.attr('data-add');
	let service_word = translate_div.attr('data-service');

	let html_tag = '<div class="all-checks" id="add_check-' + server_id + '" data-name="' + hostname + '">' +
		'<div class="check-name">' + hostname + '</div>' +
		'<div class="add_user_group check-button" onclick="addRegionToStatus(' + server_id + ',  \'' + hostname + '\')" title="' + add_word + ' ' + service_word + '">+</div></div>';
    $("#all-regions").append(html_tag);
	$('#remove_check-' + server_id).remove();
}
function createJsonCountry(div_id) {
    let jsonData = [];
    $(div_id).each(function () {
        if ($(this).attr('data-name')) {
            let this_id = $(this).attr('id').split('-')[1];
            jsonData.push(this_id);
        }
    });
    return jsonData;
}
function getCountrySettings(agent_id) {
	$.ajax({
		url: api_v_prefix + "/rmon/country/" + agent_id,
		async: false,
		success: function (data) {
			$('#new-country-name').val(data['name'].replaceAll("'", ""));
			$('#new-country-desc').val(data['description'].replaceAll("'", ""));
			$('#new-country-enabled').checkboxradio("refresh");
			if (data['enabled'] == '1') {
				$('#new-country-enabled').prop('checked', true)
			} else {
				$('#new-country-enabled').prop('checked', false)
			}
			if (data['shared'] == '1') {
				$('#new-country-shared').prop('checked', true)
			} else {
				$('#new-country-shared').prop('checked', false)
			}
			$('#new-country-enabled').checkboxradio("refresh");
			$('#new-country-shared').checkboxradio("refresh");
		}
	});
}
function getCountry(agent_id, new_country=false) {
	$.ajax({
		url: "/rmon/country/info/" + agent_id,
		success: function (data) {
			data = data.replace(/^\s+|\s+$/g, '');
			if (data.indexOf('error:') != '-1') {
				toastr.error(data);
			} else {
				if (new_country) {
					$('#smon-group-countries').append(data);
				} else {
					$('#country-' + agent_id).replaceWith(data);
				}
				$.getScript("/static/js/fontawesome.min.js");
				$('#country-' + agent_id).removeClass('animated-background');
			}
		}
	});
}
function confirmDeleteCountry(id) {
	$( "#dialog-confirm" ).dialog({
		resizable: false,
		height: "auto",
		width: 400,
		modal: true,
		title: delete_word+" " +$('#country-name-'+id).text() + "?",
		buttons: [{
			text: delete_word,
			click: function () {
				$(this).dialog("close");
				removeCountry(id, $(this));
			}
		}, {
			text: cancel_word,
			click: function() {
				$( this ).dialog( "close" );
			}
		}]
	});
}
function removeCountry(id, dialog_id) {
	$.ajax({
        url: api_v_prefix + "/rmon/country/" + id,
        type: "delete",
        data: JSON.stringify({}),
		contentType: "application/json; charset=utf-8",
		statusCode: {
			204: function (xhr) {
				toastr.clear();
                $(dialog_id).dialog("close");
				$('#country-'+id).remove();
			},
			404: function (xhr) {
				toastr.clear();
                $(dialog_id).dialog("close");
				$('#country-'+id).remove();
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
function cleanCountryAddForm() {
	$('#new-country-name').val('');
	$('#new-country-desc').val('');
	$('#new-country-shared').prop('checked', false);
	$('#new-country-enabled').prop('checked', true);
	$('#new-country-shared').checkboxradio("refresh");
	$('#new-country-enabled').checkboxradio("refresh");
	$('#checked-regions').html('');
	$('#all-regions').html('');
}
