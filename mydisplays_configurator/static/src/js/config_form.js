odoo.define('mydisplay_configurator.config_form', function (require) {
    'use strict';

    var ajax = require('web.ajax');
    var Configurator = require('website_product_configurator.config_form');

    Configurator.include({

        _onChangeDateTime: function (event) {
            var self = this;
            self._super.apply(this, arguments);
            // Call onchange for custom value(type: date/datetime)
            var field_name = $(event.currentTarget).find('.datetimepicker-input')[0].name
            self._onChangeConfigAttribute(event, field_name);
        },

        // Add new argument changed_field_name
        _onChangeConfigAttribute: function(event, changed_field_name) {
            var self = this;
            var attribute = [event.currentTarget];
            self._checkRequiredFields(attribute);
            var flag = self._checkChange(self);
            if (flag) {
                var form_data = self.config_form.serializeArray();
                for (var field_name in self.image_dict) {
                    form_data.push({'name': field_name, 'value': self.image_dict[field_name]});
                }
                $.blockUI(self.blockui_opts);
                    ajax.jsonRpc("/website_product_configurator/onchange", 'call', {
                        form_values: form_data,
                        field_name: changed_field_name || attribute[0].name,  // Customization
                    }).then(function(data) {
                        if (data.error) {
                            self.openWarningDialog(data.error);
                        } else {
                            if (data.warning) {
                                self.openWarningDialog(data.warning.message);
                            }
                            var values = data.value;
                            var domains = data.domain;
                            var dynamic_values = data.dynamic_values;

                            var open_cfg_step_line_ids = data.open_cfg_step_line_ids;
                            var config_image_vals = data.config_image_vals;

                            self._applyDomainOnValues(domains);
                            self._applyNewValues(dynamic_values)
                            self._setDataOldValId();
                            self._handleOpenSteps(open_cfg_step_line_ids);
                            self._setImageUrl(config_image_vals);
                            self._setWeightPrice(values.weight, values.price, data.decimal_precision);
                        };
                        if ($.blockUI) {
                            $.unblockUI();
                        }
                    });
                    self._handleCustomAttribute(event)
            };
        },

        _applyNewValues: function (dynamic_values) {
            _.each(dynamic_values, function (value, key) {
                var option = $('select#' + key).find(".config_attr_value[data-oe-id=" + value + "]");
                if (option.length) {
                    option[0].selected = true;
                };
                var option = $('fieldset#' + key).find(".config_attr_value[data-oe-id=" + value + "]");
                if (option.length) {
                    option[0].checked = true;
                };
            });
        },

        _onChangeCustomField: function(event) {
            var self = this;
            self._super.apply(this, arguments);
            // Call onchange for custom value(type: char/textarea/color)
            var current_field = $(event.currentTarget)
            if(current_field.hasClass('config_attachment') || current_field.hasClass('spinner_qty')) {
                return
            }
            var field_name = event.currentTarget.name
            self._onChangeConfigAttribute(event, field_name);
        },

        _onChangeFile: function (ev) {
            var self = this;
            var result = self._super.apply(this, arguments);
            // Call onchange for custom value(type: binary)
            result.done(function() {
                var field_name = ev.currentTarget.name
                self._onChangeConfigAttribute(ev, field_name);
                return result;
            })
        },

        _handleSppinerCustomValue: function (ev) {
            var self = this;
            var custom_value = self._super.apply(this, arguments);
            // Call onchange for custom value(type: integer/float)
            var field_name = $(ev.currentTarget).closest('.custom_field_container').find('.custom_config_value.spinner_qty')[0].name
            self._onChangeConfigAttribute(ev, field_name);
            return custom_value;
        },
    })
})
