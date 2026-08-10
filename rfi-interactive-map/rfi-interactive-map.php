<?php
/**
 * Plugin Name: RFI Interactive Map
 * Description: An accessible public map whose layer manifest can be served from a published Git repository.
 * Version: 1.1.99
 * Requires at least: 6.2
 * Requires PHP: 7.4
 * Text Domain: rfi-interactive-map
 */

if (!defined('ABSPATH')) {
    exit;
}

const RFI_MAP_VERSION = '1.1.99';
const RFI_MAP_MANIFEST_OPTION = 'rfi_map_manifest_url';

/**
 * Only allow an empty value (the bundled fallback) or a public HTTPS URL.
 */
function rfi_map_sanitize_manifest_url($value) {
    $value = trim((string) $value);
    if ($value === '') {
        return '';
    }

    $url = esc_url_raw($value, array('https'));
    if (!$url || strtolower((string) wp_parse_url($url, PHP_URL_SCHEME)) !== 'https') {
        add_settings_error(
            RFI_MAP_MANIFEST_OPTION,
            'rfi_map_manifest_url_invalid',
            __('Enter a complete HTTPS URL for the repository manifest.', 'rfi-interactive-map')
        );
        return (string) get_option(RFI_MAP_MANIFEST_OPTION, '');
    }

    return $url;
}

function rfi_map_register_settings() {
    register_setting(
        'rfi_map_settings',
        RFI_MAP_MANIFEST_OPTION,
        array(
            'type' => 'string',
            'default' => '',
            'sanitize_callback' => 'rfi_map_sanitize_manifest_url',
        )
    );
}
add_action('admin_init', 'rfi_map_register_settings');

function rfi_map_add_settings_page() {
    add_options_page(
        __('RFI Map', 'rfi-interactive-map'),
        __('RFI Map', 'rfi-interactive-map'),
        'manage_options',
        'rfi-map',
        'rfi_map_render_settings_page'
    );
}
add_action('admin_menu', 'rfi_map_add_settings_page');

function rfi_map_render_settings_page() {
    if (!current_user_can('manage_options')) {
        return;
    }
    $manifest_url = (string) get_option(RFI_MAP_MANIFEST_OPTION, '');
    ?>
    <div class="wrap">
        <h1><?php esc_html_e('RFI Interactive Map', 'rfi-interactive-map'); ?></h1>
        <p><?php esc_html_e('Choose the map manifest stored in your published Git repository. Leave the field empty to use the data packaged with this plugin.', 'rfi-interactive-map'); ?></p>
        <form action="options.php" method="post">
            <?php settings_fields('rfi_map_settings'); ?>
            <table class="form-table" role="presentation">
                <tr>
                    <th scope="row">
                        <label for="rfi-map-manifest-url"><?php esc_html_e('Raw manifest URL', 'rfi-interactive-map'); ?></label>
                    </th>
                    <td>
                        <input
                            id="rfi-map-manifest-url"
                            name="<?php echo esc_attr(RFI_MAP_MANIFEST_OPTION); ?>"
                            type="url"
                            class="regular-text code"
                            value="<?php echo esc_attr($manifest_url); ?>"
                            placeholder="https://raw.githubusercontent.com/organization/map-data/main/map-config.json"
                        >
                        <p class="description"><?php esc_html_e('Use the raw-file URL, not the repository web page. Relative layer paths in the manifest are resolved from this URL.', 'rfi-interactive-map'); ?></p>
                    </td>
                </tr>
            </table>
            <?php submit_button(); ?>
        </form>
        <h2><?php esc_html_e('Embed the map', 'rfi-interactive-map'); ?></h2>
        <p><code>[rfi_interactive_map]</code></p>
        <p><?php esc_html_e('Optional attributes:', 'rfi-interactive-map'); ?> <code>height="720px"</code>, <code>title="Property map"</code>, <code>data_url="https://…/map-config.json"</code>.</p>
    </div>
    <?php
}

function rfi_interactive_map_assets() {
    $base = plugin_dir_url(__FILE__);
    wp_enqueue_style('leaflet', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', array(), '1.9.4');
    wp_enqueue_style('rfi-map', $base . 'assets/rfi-map.css', array('leaflet'), RFI_MAP_VERSION);
    wp_enqueue_script('leaflet', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', array(), '1.9.4', true);
    wp_enqueue_script('leaflet-rotate', $base . 'assets/leaflet-rotate.js', array('leaflet'), '0.2.8', true);
    wp_enqueue_script('rfi-map', $base . 'assets/rfi-map.js', array('leaflet', 'leaflet-rotate'), RFI_MAP_VERSION, true);
}

function rfi_interactive_map_shortcode($atts) {
    rfi_interactive_map_assets();
    $base = plugin_dir_url(__FILE__);
    $atts = shortcode_atts(
        array(
            'height' => '680px',
            'title' => __('Interactive map', 'rfi-interactive-map'),
            'data_url' => '',
        ),
        $atts,
        'rfi_interactive_map'
    );

    $configured_url = (string) get_option(RFI_MAP_MANIFEST_OPTION, '');
    $attribute_url = rfi_map_sanitize_manifest_url($atts['data_url']);
    $config_url = $attribute_url ?: ($configured_url ?: $base . 'data/map-config.json');
    $height = preg_match('/^\d+(?:\.\d+)?(?:px|vh|vw|rem|em|%)$/', (string) $atts['height']) ? $atts['height'] : '680px';
    $title = sanitize_text_field((string) $atts['title']);

    ob_start();
    ?>
    <section
        class="rfi-map"
        style="--rfi-map-height:<?php echo esc_attr($height); ?>"
        data-config-url="<?php echo esc_url($config_url); ?>"
        aria-label="<?php echo esc_attr($title); ?>"
    >
        <div class="rfi-map__canvas" aria-label="<?php esc_attr_e('Interactive map', 'rfi-interactive-map'); ?>"></div>
        <nav class="rfi-map__sections" aria-label="<?php esc_attr_e('Map sections', 'rfi-interactive-map'); ?>">
            <button type="button" class="rfi-map__section-tab" data-rfi-section="land-use" aria-pressed="true"><?php esc_html_e('Land use', 'rfi-interactive-map'); ?></button>
            <button type="button" class="rfi-map__section-tab" data-rfi-section="contours" aria-pressed="false"><?php esc_html_e('Elevation and watershed', 'rfi-interactive-map'); ?></button>
            <button type="button" class="rfi-map__section-tab" data-rfi-section="monkey-study" aria-pressed="false"><?php esc_html_e('Monkey study', 'rfi-interactive-map'); ?></button>
            <button type="button" class="rfi-map__section-tab" data-rfi-section="environmental-health-analysis" aria-pressed="false"><?php esc_html_e('Environmental health analysis', 'rfi-interactive-map'); ?></button>
        </nav>
        <span class="rfi-map__status screen-reader-text" role="status" aria-live="polite"><?php esc_html_e('Loading map data…', 'rfi-interactive-map'); ?></span>
        <div class="rfi-map__layer-store" hidden aria-hidden="true">
            <div class="rfi-map__layers"></div>
            <div class="rfi-map__assets"></div>
        </div>
        <div class="rfi-map__loading" aria-hidden="true"><span></span></div>
    </section>
    <?php
    return ob_get_clean();
}
add_shortcode('rfi_interactive_map', 'rfi_interactive_map_shortcode');
