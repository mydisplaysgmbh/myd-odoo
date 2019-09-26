odoo.define('mydisplay_configurator.config_form', function (require) {
    'use strict';

    var ajax = require('web.ajax');
    var time = require('web.time');
    var utils = require('web.utils');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var _t = core._t;

    var image_dict = {}

    $(document).ready(function () {

        var config_form = $("#product_config_form");

        function OnchangeVals(ev, fild_name) {
            var form_data = config_form.serializeArray();
            for (var field_name in image_dict) {
                form_data.push({'name': field_name, 'value': image_dict[field_name]});
            }
            ajax.jsonRpc("/website_product_configurator/onchange", 'call', {
                form_values: form_data,
                field_name: fild_name,
            }).then(function(data) {
                if (data.error) {
                    openWarningDialog(data.error);
                } else {
                    var values = data.value;
                    var domains = data.domain;

                    var open_cfg_step_line_ids = data.open_cfg_step_line_ids;
                    var config_image_vals = data.config_image_vals;

                    _applyDomainOnValues(domains);
                    _handleOpenSteps(open_cfg_step_line_ids);
                    _setImageUrl(config_image_vals);
                    _setWeightPrice(values.weight, values.price, data.decimal_precision);
                };
            });
            _handleCustomAttribute(ev)
        }

        /* Monitor input changes in the configuration form and call the backend onchange method*/
        config_form.find('.custom_config_value').change(function(ev) {
            ev.preventDefault();
            ev.stopPropagation();
            OnchangeVals(ev, $(this)[0].name)
        });
        config_form.find('.product_config_datepicker').parent().on('change.datetimepicker', function (event) {
            OnchangeVals(event, $('.product_config_datepicker')[0].name)
        });
        config_form.find('.product_config_datetimepicker').parent().on('change.datetimepicker', function (event) {
            OnchangeVals(event, $('.product_config_datepicker')[0].name)
        });
        $('.js_add_qty').on('click', function(ev) {
            OnchangeVals(event, $('.custom_config_value.spinner_qty')[0].name)
        });

        $('.js_remove_qty').on('click', function(ev) {
            OnchangeVals(event, $('.custom_config_value.spinner_qty')[0].name)
        });

        config_form.find('.custom_config_value.config_attachment').change(function (ev) {
            var file = ev.target.files[0];
            var loaded = false;
            var files_data = '';
            var BinaryReader = new FileReader();
            // file read as DataURL
            BinaryReader.readAsDataURL(file);
            BinaryReader.onloadend = function (upload) {
                var buffer = upload.target.result;
                buffer = buffer.split(',')[1];
                files_data = buffer;
                image_dict[ev.target.name]= files_data;
            }
        });

        function openWarningDialog(message) {
            var dialog = new Dialog(config_form, {
                title: "Warning!!!",
                size: 'medium',
                $content: "<div>" + message + "</div>",
            }).open();
        }

        function price_to_str(price, precision) {
            var l10n = _t.database.parameters;
            var formatted = _.str.sprintf('%.' + precision + 'f', price).split('.');
            formatted[0] = utils.insert_thousand_seps(formatted[0]);
            return formatted.join(l10n.decimal_point);
        };

        function weight_to_str(weight, precision) {
            var l10n = _t.database.parameters;
            var formatted = _.str.sprintf('%.' + precision + 'f', weight).split('.');
            formatted[0] = utils.insert_thousand_seps(formatted[0]);
            return formatted.join(l10n.decimal_point);
        };

        function _setWeightPrice(weight, price, decimal_precisions) {
            var formatted_price = price_to_str(price, decimal_precisions.price);
            var formatted_weight = weight_to_str(weight, decimal_precisions.weight);
            $('.config_product_weight').text(formatted_weight);
            $('.config_product_price').find('.oe_currency_value').text(formatted_price);
        };

        function _setImageUrl(config_image_vals) {
            var images = '';
            if (config_image_vals){
                var model = config_image_vals.name
                config_image_vals.config_image_ids.forEach(function(line){
                    images += "<img id='cfg_image' itemprop='image' class='img img-responsive pull-right'"
                    images += "src='/web/image/"+model+"/"+line+"/image'/>"
                })
            }
            $('#product_config_image').html(images);
        };

        function _handleCustomAttribute(event) {
            var container = $(event.currentTarget).closest('.tab-pane.container');
            var attribute_id = $(event.currentTarget).attr('data-oe-id');
            var custom_value = container.find('.custom_config_value[data-oe-id=' + attribute_id + ']');
            var custom_value_container = custom_value.closest('.custom_field_container[data-oe-id=' + attribute_id + ']');
            var attr_field = container.find('.config_attribute[data-oe-id=' + attribute_id + ']');
            var custom_config_attr = attr_field.find('.custom_config_attr_value');
            var flag_custom = false;
            if (custom_config_attr.length && custom_config_attr[0].tagName == "OPTION" && custom_config_attr[0].selected) {
                flag_custom = true;
            } else if (custom_config_attr.length && custom_config_attr[0].tagName == "INPUT" && custom_config_attr[0].checked) {
                flag_custom = true;
            };
            if (flag_custom && custom_value_container.hasClass('d-none')) {
                custom_value_container.removeClass('d-none');
                custom_value.addClass('required_config_attrib');
            } else if (!flag_custom && !custom_value_container.hasClass('d-none')){
                custom_value_container.addClass('d-none');
                if (custom_value.hasClass('required_config_attrib')) {
                    custom_value.removeClass('required_config_attrib');
                }
            }
        }

        function _handleOpenSteps(open_cfg_step_line_ids) {
            var $steps = config_form.find('.config_step');
            _.each($steps, function (step) {
                step = $(step);
                var step_id = step.attr('data-step-id');
                if ($.inArray(step_id, open_cfg_step_line_ids) < 0) {
                    if (!step.hasClass('d-none')) {
                        step.addClass('d-none');
                    };
                } else {
                    if (step.hasClass('d-none')) {
                        step.removeClass('d-none');
                    };
                };
            });
        }

        function _applyDomainOnValues(domains) {
            _.each(domains, function (domain, attr_id) {
                var $selection = config_form.find('#' + attr_id);
                var $options = $selection.find('.config_attr_value');
                _.each($options, function (option) {
                    var condition = domain[0][1];
                    if (condition == 'in' || condition == '=') {
                        if ($.inArray(parseInt(option.value), domain[0][2]) < 0) {
                            $(option).attr('disabled', true);
                            if (option.selected) {
                                option.selected = false;
                            } else if (option.checked) {
                                option.checked = false;
                            };
                        } else {
                            $(option).attr('disabled', false);
                        };
                    } else if (condition == 'not in' || condition == '!=') {
                        if ($.inArray(parseInt(option.value), domain[0][2]) < 0) {
                            $(option).attr('disabled', false);
                        } else {
                            $(option).attr('disabled', true);
                            if (option.selected) {
                                option.selected = false;
                            } else if (option.checked) {
                                option.checked = false;
                            };
                        };
                    };
                });
            });
        }
    })
})
